package com.diegoz.a2uiconcierge.a2ui

import android.content.Context
import android.content.ContextWrapper
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.fragment.app.FragmentActivity
import com.diegoz.a2uiconcierge.BuildConfig
import com.diegoz.a2uiconcierge.x402.SecureWallet
import com.diegoz.a2uiconcierge.x402.X402Signer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

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
     * x402 settle bridge. The JS gives us the *unsigned* challenge object;
     * Kotlin owns the EIP-3009 signing (StrongBox-wrapped seed +
     * biometric per op) and the HTTP POST to /x402/settle. Result lands
     * back in JS via `evaluateJavascript` on a window-scoped callback.
     *
     * Two prompts on first use: one to create the wallet (set up the
     * StrongBox key + encrypt the seed), one to decrypt for signing.
     * Every subsequent payment is a single prompt.
     */
    @JavascriptInterface
    fun settle(orderId: String, challengeJson: String, callbackName: String) {
        Log.d(TAG, "settle: order=$orderId cb=$callbackName")
        scope.launch {
            val resultJson = try {
                val activity = currentActivity()
                    ?: error("No FragmentActivity in WebView context")
                val challenge = JSONObject(challengeJson)
                val wallet = SecureWallet(activity)
                if (!wallet.hasWallet()) wallet.createWallet(activity)
                val envelope = wallet.withSeed(activity) { seed ->
                    X402Signer(seed).signEnvelope(challenge)
                }
                val body = JSONObject().apply {
                    put("order_id", orderId)
                    put("envelope", envelope)
                }.toString()
                val req = Request.Builder()
                    .url("$BACKEND_BASE_URL/x402/settle")
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .build()
                http.newCall(req).execute().use { resp ->
                    val text = resp.body?.string().orEmpty()
                    if (resp.isSuccessful) text else jsonError("HTTP ${resp.code}: $text")
                }
            } catch (e: Exception) {
                Log.e(TAG, "settle failed", e)
                jsonError(e.message ?: e::class.java.simpleName)
            }

            withContext(Dispatchers.Main) {
                webView?.evaluateJavascript(
                    "window['${callbackName.replace("'", "")}']($resultJson);",
                    null,
                )
            }
        }
    }

    /** Unwrap the WebView's context chain to find the hosting activity. */
    private fun currentActivity(): FragmentActivity? {
        var c: Context = webView?.context ?: return null
        while (c is ContextWrapper) {
            if (c is FragmentActivity) return c
            c = c.baseContext
        }
        return null
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
