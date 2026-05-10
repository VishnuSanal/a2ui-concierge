package com.diegoz.a2uiconcierge.a2ui

import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.diegoz.a2uiconcierge.BuildConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

class A2uiBridge {
    val actions = Channel<String>(capacity = Channel.UNLIMITED)
    val resizes = Channel<Int>(capacity = Channel.CONFLATED)

    // Assigned by the AndroidView factory once the WebView exists, so the
    // bridge can deliver async settle results back into the JS runtime via
    // evaluateJavascript on the main thread.
    @Volatile var webView: WebView? = null

    @JavascriptInterface
    fun onAction(json: String) {
        Log.d(TAG, "onAction: $json")
        actions.trySend(json)
    }

    @JavascriptInterface
    fun onResize(heightPx: Int) {
        Log.d(TAG, "onResize: $heightPx px")
        resizes.trySend(heightPx)
    }

    @JavascriptInterface
    fun log(msg: String) {
        Log.d(TAG, "JS: $msg")
    }

    /**
     * x402 settle bridge. The web component cannot fetch the backend directly
     * from a file:// origin (Android blocks cleartext + cross-origin from the
     * WebView), so the JS calls into Kotlin and Kotlin owns the HTTP. Result
     * is delivered back to the JS callback via evaluateJavascript.
     *
     * Phase 2 hooks here: replace `signed_envelope = envelopeJson` with a
     * StrongBox-backed EIP-3009 signature before posting.
     */
    @JavascriptInterface
    fun settle(orderId: String, envelopeJson: String, callbackName: String) {
        Log.d(TAG, "settle: order=$orderId cb=$callbackName")
        scope.launch {
            val resultJson = try {
                val body = """{"order_id":"${orderId.replace("\"", "\\\"")}","envelope":$envelopeJson}"""
                val req = Request.Builder()
                    .url("$BACKEND_BASE_URL/x402/settle")
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .build()
                http.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.isSuccessful) text else jsonError("HTTP ${resp.code}: $text")
                }
            } catch (e: Exception) {
                jsonError(e.message ?: "fetch failed")
            }

            withContext(Dispatchers.Main) {
                webView?.evaluateJavascript(
                    "window['${callbackName.replace("'", "")}']($resultJson);",
                    null,
                )
            }
        }
    }

    private fun jsonError(msg: String): String {
        val safe = msg.replace("\\", "\\\\").replace("\"", "\\\"").take(400)
        return """{"error":"$safe"}"""
    }

    private companion object {
        const val TAG = "A2uiBridge"
        // adb reverse tcp:8000 makes the laptop backend reachable here.
        val BACKEND_BASE_URL: String = BuildConfig.BACKEND_BASE_URL
        val http = OkHttpClient()
        val scope = CoroutineScope(Dispatchers.IO)
    }
}
