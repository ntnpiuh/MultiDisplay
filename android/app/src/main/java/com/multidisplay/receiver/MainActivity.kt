package com.multidisplay.receiver

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var root: LinearLayout
    private lateinit var address: EditText
    private lateinit var port: EditText
    private lateinit var status: TextView
    private var webView: WebView? = null
    private var customView: View? = null
    private var customViewCallback: WebChromeClient.CustomViewCallback? = null
    private var startingUsb = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        buildConnectView()
    }

    private fun buildConnectView() {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(32), dp(24), dp(24))
            setBackgroundColor(Color.rgb(244, 241, 232))
        }
        root.addView(TextView(this).apply {
            text = "MultiDisplay"
            textSize = 30f
            setTextColor(Color.rgb(23, 35, 31))
        })
        root.addView(TextView(this).apply {
            text = "Connect this Android device as an extended Mac display."
            textSize = 16f
            setTextColor(Color.rgb(70, 84, 76))
            setPadding(0, dp(8), 0, dp(24))
        })
        root.addView(TextView(this).apply {
            text = "Mac address (Wi-Fi)"
            textSize = 13f
            setTextColor(Color.rgb(70, 84, 76))
        })
        address = EditText(this).apply {
            hint = "192.168.1.25"
            setSingleLine(true)
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
            setTextColor(Color.rgb(23, 35, 31))
            setBackgroundColor(Color.WHITE)
            setPadding(dp(12), dp(8), dp(12), dp(8))
        }
        root.addView(address, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(6) })
        root.addView(TextView(this).apply {
            text = "Receiver port"
            textSize = 13f
            setTextColor(Color.rgb(70, 84, 76))
            setPadding(0, dp(12), 0, 0)
        })
        port = EditText(this).apply {
            hint = "51820"
            setText("51820")
            setSingleLine(true)
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            setTextColor(Color.rgb(23, 35, 31))
            setBackgroundColor(Color.WHITE)
            setPadding(dp(12), dp(8), dp(12), dp(8))
        }
        root.addView(port, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(6) })
        root.addView(makeButton("Connect over Wi-Fi") {
            startingUsb = false
            val host = address.text.toString().trim().removePrefix("http://").removePrefix("https://").substringBefore('/')
            val receiverPort = port.text.toString().toIntOrNull()
            if (host.isBlank() || host.contains(' ') || receiverPort == null || receiverPort !in 1..65535) {
                status.text = "Enter the Mac's Wi-Fi IP address and a valid receiver port."
            } else {
                openReceiver("http://$host:$receiverPort/receiver")
            }
        }, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(14) })
        root.addView(makeButton("Connect over USB") {
            startingUsb = true
            status.text = "Connect the USB data cable and approve USB debugging on both devices."
            val receiverPort = port.text.toString().toIntOrNull()
            if (receiverPort == null || receiverPort !in 1..65535) {
                status.text = "Enter a receiver port from 1 to 65535."
            } else {
                openReceiver("http://127.0.0.1:$receiverPort/receiver")
            }
        }, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(14) })
        root.addView(TextView(this).apply {
            text = "USB needs USB debugging enabled and an approved Mac so it can create a direct USB data tunnel."
            textSize = 13f
            setTextColor(Color.rgb(104, 119, 112))
            setPadding(0, dp(6), 0, dp(8))
        })
        status = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.rgb(164, 77, 46))
            setPadding(0, dp(12), 0, 0)
        }
        root.addView(status)
        setContentView(root)
    }

    private fun makeButton(label: String, action: () -> Unit): Button = Button(this).apply {
        text = label
        isAllCaps = false
        setTextColor(Color.WHITE)
        setBackgroundColor(Color.rgb(40, 115, 94))
        setOnClickListener { action() }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun openReceiver(url: String) {
        val isUsbConnection = startingUsb
        var usbRetryCount = 0
        val receiverView = WebView(this)
        receiverView.apply {
            setBackgroundColor(Color.rgb(16, 23, 20))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            settings.mediaPlaybackRequiresUserGesture = false
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            settings.displayZoomControls = false
            settings.useWideViewPort = false
            settings.loadWithOverviewMode = false
            settings.textZoom = 100
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, loadedUrl: String) {
                    status.text = ""
                }
                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) {
                        if (isUsbConnection && usbRetryCount < 20) {
                            usbRetryCount += 1
                            status.text = "Waiting for the USB tunnel… ($usbRetryCount/20)"
                            view.postDelayed({ view.loadUrl(url) }, 1000)
                            return
                        }
                        val message = if (isUsbConnection) {
                            "USB tunnel did not start. Confirm USB debugging and the Mac's ADB approval."
                        } else {
                            "Could not reach the Mac. Check both devices are on the same Wi-Fi network."
                        }
                        status.text = message
                        Toast.makeText(this@MainActivity, message, Toast.LENGTH_LONG).show()
                    }
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                    if (customView != null) {
                        callback.onCustomViewHidden()
                        return
                    }
                    customView = view
                    customViewCallback = callback
                    (this@MainActivity.window.decorView as ViewGroup).addView(view, ViewGroup.LayoutParams(-1, -1))
                    this@MainActivity.window.decorView.systemUiVisibility = (
                        View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        )
                }
                override fun onHideCustomView() {
                    leaveCustomView()
                }
            }
            loadUrl(url)
        }
        webView = receiverView
        setContentView(receiverView)
    }

    override fun onBackPressed() {
        if (customView != null) {
            leaveCustomView()
        } else if (webView != null) {
            webView?.stopLoading()
            webView?.destroy()
            webView = null
            buildConnectView()
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        closeReceiver()
        webView?.destroy()
        super.onDestroy()
    }

    override fun onStop() {
        if (!isChangingConfigurations) {
            closeReceiver()
        }
        super.onStop()
    }

    private fun closeReceiver() {
        webView?.evaluateJavascript("window.dispatchEvent(new Event('pagehide'))", null)
        webView?.stopLoading()
    }

    private fun leaveCustomView() {
        (customView?.parent as? ViewGroup)?.removeView(customView)
        customView = null
        customViewCallback?.onCustomViewHidden()
        customViewCallback = null
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
