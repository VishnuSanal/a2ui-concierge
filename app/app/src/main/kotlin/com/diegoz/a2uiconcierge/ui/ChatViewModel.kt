package com.diegoz.a2uiconcierge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.diegoz.a2uiconcierge.chat.AgentEvent
import com.diegoz.a2uiconcierge.chat.ChatRepository
import com.diegoz.a2uiconcierge.chat.CredentialRequestData
import com.diegoz.a2uiconcierge.chat.Message
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.UUID

/**
 * Bridges the SSE event stream to the UI:
 *
 *  • Buffers v0.8 A2UI messages per ``surfaceId`` until ``beginRendering``
 *    arrives, then commits the full (surfaceUpdate, beginRendering, ...)
 *    bundle to a chat bubble — or routes it to a modal sheet for the
 *    product-detail / payment-challenge surfaces.
 *  • Translates the v0.8 ``userAction`` envelope coming back from the
 *    WebView bridge into the legacy ``[ui-action] {component, ...context}``
 *    string the agent's prompts continue to use.
 */
class ChatViewModel(private val repo: ChatRepository) : ViewModel() {

    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()

    private val _isThinking = MutableStateFlow(false)
    val isThinking: StateFlow<Boolean> = _isThinking.asStateFlow()

    private val _credentialRequest = MutableSharedFlow<CredentialRequestData>(extraBufferCapacity = 1)
    val credentialRequest: SharedFlow<CredentialRequestData> = _credentialRequest.asSharedFlow()

    private val _productDetail = MutableStateFlow<List<JsonObject>?>(null)
    val productDetail: StateFlow<List<JsonObject>?> = _productDetail.asStateFlow()

    private val _paymentChallenge = MutableStateFlow<List<JsonObject>?>(null)
    val paymentChallenge: StateFlow<List<JsonObject>?> = _paymentChallenge.asStateFlow()

    private val _txDetail = MutableStateFlow<List<JsonObject>?>(null)
    val txDetail: StateFlow<List<JsonObject>?> = _txDetail.asStateFlow()

    fun onA2uiAction(json: String) {
        val action = extractUserAction(json) ?: return
        val name = action.name
        val context = action.context

        // Pure UI dismiss — don't forward, don't echo.
        when (name) {
            "product-detail-close" -> { _productDetail.value = null; return }
            "payment-challenge-close" -> { _paymentChallenge.value = null; return }
            "tx-detail-close" -> { _txDetail.value = null; return }
        }

        // Confirmation card's "view tx" tap is a pure client-side navigation:
        // build a TxDetail surface from the action context and pop the sheet.
        if (name == "tx-detail-open") {
            _txDetail.value = buildTxDetailSurface(context)
            return
        }

        // Successful payment dismisses the modal payment sheet; the agent
        // will follow up with the confirmation card.
        if (name == "payment-completed") _paymentChallenge.value = null

        val legacy = legacyPayload(name, context)
        val display = humanizeAction(name, context)
        _messages.update { it + Message.User(UUID.randomUUID().toString(), display) }
        if (name == "product-detail" || name == "product-detail-followup"
            || name == "product-detail-visit") {
            _productDetail.value = null
        }
        sendInternal("[ui-action] $legacy")
    }

    fun dismissProductDetail() { _productDetail.value = null }
    fun dismissPaymentChallenge() { _paymentChallenge.value = null }
    fun dismissTxDetail() { _txDetail.value = null }

    fun send(text: String) {
        if (text.isBlank()) return
        _messages.update { it + Message.User(UUID.randomUUID().toString(), text) }
        sendInternal(text)
    }

    fun submitCredential(credentialToken: String?, dcqlQueryJson: String?) {
        viewModelScope.launch {
            try {
                repo.submitCredential(credentialToken, dcqlQueryJson)
            } catch (e: Exception) {
                val msg = "⚠️ Credential submission failed: ${e.message}"
                _messages.update { it + Message.AgentText(UUID.randomUUID().toString(), msg) }
            }
        }
    }

    private fun sendInternal(text: String) {
        viewModelScope.launch {
            _isThinking.value = true
            try {
                var textBubbleId: String? = null
                // Per-turn buffer of surface frames keyed by surfaceId.
                // Each surface is committed once its beginRendering frame
                // arrives, then dropped from the buffer.
                val pendingSurfaces = mutableMapOf<String, MutableList<JsonObject>>()

                repo.send(text).collect { ev ->
                    when (ev) {
                        is AgentEvent.Text -> {
                            if (textBubbleId == null) {
                                val id = UUID.randomUUID().toString()
                                textBubbleId = id
                                _messages.update { it + Message.AgentText(id, ev.text) }
                            } else {
                                _messages.update { list ->
                                    list.map { m ->
                                        if (m is Message.AgentText && m.id == textBubbleId) {
                                            m.copy(markdown = m.markdown + ev.text)
                                        } else m
                                    }
                                }
                            }
                        }
                        is AgentEvent.A2ui -> {
                            textBubbleId = null
                            handleA2uiMessage(ev.payload, pendingSurfaces)
                        }
                        is AgentEvent.CredentialRequest -> {
                            _credentialRequest.emit(ev.data)
                        }
                        AgentEvent.End -> Unit
                    }
                }
            } catch (e: Exception) {
                val msg = "⚠️ ${e::class.java.simpleName}: ${e.message ?: "request failed"}"
                _messages.update { it + Message.AgentText(UUID.randomUUID().toString(), msg) }
            } finally {
                _isThinking.value = false
            }
        }
    }

    private fun handleA2uiMessage(
        frame: JsonObject,
        pending: MutableMap<String, MutableList<JsonObject>>,
    ) {
        val surfaceId = surfaceIdOf(frame) ?: return
        val frames = pending.getOrPut(surfaceId) { mutableListOf() }
        frames.add(frame)
        if (frame.containsKey("beginRendering")) {
            val componentType = rootComponentType(frames)
            val finalFrames = frames.toList()
            pending.remove(surfaceId)
            when (componentType) {
                "ProductDetail" -> _productDetail.value = finalFrames
                "PaymentChallenge" -> _paymentChallenge.value = finalFrames
                else -> _messages.update {
                    it + Message.AgentA2ui(UUID.randomUUID().toString(), finalFrames)
                }
            }
        } else if (frame.containsKey("deleteSurface")) {
            pending.remove(surfaceId)
            // Bubbles that have already been committed stay; v0.8
            // deleteSurface is mostly meaningful for live multi-surface
            // streams which the demo never produces.
        }
    }

    private fun surfaceIdOf(frame: JsonObject): String? {
        val inner = (frame["surfaceUpdate"] as? JsonObject)
            ?: (frame["beginRendering"] as? JsonObject)
            ?: (frame["dataModelUpdate"] as? JsonObject)
            ?: (frame["deleteSurface"] as? JsonObject)
            ?: return null
        return inner["surfaceId"]?.jsonPrimitive?.contentOrNull
    }

    private fun rootComponentType(frames: List<JsonObject>): String? {
        // v0.8: beginRendering.root names the authoritative root component id;
        // surfaceUpdate.components may be in any order, so look up by id
        // instead of taking the first entry.
        val rootId = frames.firstNotNullOfOrNull { f ->
            (f["beginRendering"] as? JsonObject)
                ?.get("root")?.jsonPrimitive?.contentOrNull
        } ?: return null
        for (f in frames) {
            val update = f["surfaceUpdate"] as? JsonObject ?: continue
            val components = update["components"] as? JsonArray ?: continue
            for (item in components) {
                val obj = item as? JsonObject ?: continue
                if (obj["id"]?.jsonPrimitive?.contentOrNull != rootId) continue
                val componentObj = obj["component"] as? JsonObject ?: continue
                return componentObj.keys.firstOrNull()
            }
        }
        return null
    }

    // ── userAction envelope ↔ legacy [ui-action] translation ──────────

    private data class UserAction(val name: String, val context: JsonObject)

    private fun extractUserAction(json: String): UserAction? = try {
        val obj = Json.parseToJsonElement(json) as? JsonObject ?: return null
        val ua = obj["userAction"] as? JsonObject ?: return null
        val name = ua["name"]?.jsonPrimitive?.contentOrNull ?: return null
        val ctx = (ua["context"] as? JsonObject) ?: JsonObject(emptyMap())
        UserAction(name, ctx)
    } catch (_: Exception) { null }

    /** Compose ``{"component": <name>, ...context}`` JSON the agent expects. */
    private fun legacyPayload(name: String, context: JsonObject): String {
        val merged = LinkedHashMap<String, JsonElement>()
        merged["component"] = JsonPrimitive(name)
        for ((k, v) in context) merged[k] = v
        return JsonObject(merged).toString()
    }

    private fun humanizeAction(name: String, context: JsonObject): String {
        fun str(k: String) = context[k]?.jsonPrimitive?.contentOrNull
        return when (name) {
            "chip-group" -> str("value")?.replaceFirstChar { it.titlecase() } ?: "Selection"
            "card-grid" -> str("name") ?: "View item"
            "product-detail" -> "Add ${str("name") ?: "item"} to order"
            "product-detail-followup" -> "Tell me more about ${str("name") ?: "this"}"
            "product-detail-visit" -> "Visit ${str("vendor") ?: "vendor"}"
            "form" -> "Place order"
            "confirmation-card" -> "Confirmed"
            "payment-completed" -> "Paid"
            else -> "Selection"
        }
    }

    /**
     * Build a synthetic A2UI surface bundle for a TxDetail bubble from
     * the tx-detail-open action's context. Uses the same v0.8 wire shape
     * (surfaceUpdate + beginRendering) so the same WebView interpreter
     * renders the modal sheet without a server round-trip.
     */
    private fun buildTxDetailSurface(context: JsonObject): List<JsonObject> {
        val sid = "tx-${UUID.randomUUID().toString().take(8)}"
        val rid = "c-tx-${UUID.randomUUID().toString().take(6)}"
        // Wrap a string into a v0.8 BoundValue. Source strings that aren't
        // present are simply omitted from the props map — an empty object
        // is *not* a valid BoundValue and the shim would resolve it as a
        // truthy literal, breaking string-typed props in the WebView.
        fun bound(v: String): JsonElement =
            JsonObject(mapOf("literalString" to JsonPrimitive(v)))
        val props = LinkedHashMap<String, JsonElement>()
        props["orderId"] = context["order_id"] ?: JsonPrimitive("")
        context["tx_hash"]?.jsonPrimitive?.contentOrNull?.let { props["txHash"] = bound(it) }
        context["explorer_url"]?.jsonPrimitive?.contentOrNull?.let { props["explorerUrl"] = bound(it) }
        context["ship_date"]?.jsonPrimitive?.contentOrNull?.let { props["shipDate"] = bound(it) }
        context["items"]?.let { props["items"] = it }
        context["total"]?.let { props["total"] = it }
        val component = JsonObject(mapOf("TxDetail" to JsonObject(props)))
        val componentDef = JsonObject(mapOf(
            "id" to JsonPrimitive(rid),
            "component" to component,
        ))
        val surfaceUpdate = JsonObject(mapOf(
            "surfaceUpdate" to JsonObject(mapOf(
                "surfaceId" to JsonPrimitive(sid),
                "components" to JsonArray(listOf(componentDef)),
            ))
        ))
        val beginRendering = JsonObject(mapOf(
            "beginRendering" to JsonObject(mapOf(
                "surfaceId" to JsonPrimitive(sid),
                "root" to JsonPrimitive(rid),
                "catalogId" to JsonPrimitive("lumen.com:concierge/v1"),
            ))
        ))
        return listOf(surfaceUpdate, beginRendering)
    }
}
