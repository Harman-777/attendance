package in.agclms.ultraportal;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.Window;
import android.view.WindowManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import java.net.URLEncoder;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {

    private static final String PORTAL_URL = "https://attendance-liard-three.vercel.app";
    private static final int DARK_BG_COLOR = 0xFF090D16;
    private WebView webView;

    public class WebAppInterface {
        private final Activity activity;

        WebAppInterface(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public String getAppVersion() {
            return "2.1";
        }

        @JavascriptInterface
        public int getAppVersionCode() {
            return 3;
        }

        @JavascriptInterface
        public void printPage() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    PrintManager printManager = (PrintManager) activity.getSystemService(Context.PRINT_SERVICE);
                    if (printManager != null && webView != null) {
                        PrintDocumentAdapter printAdapter = webView.createPrintDocumentAdapter("UltraPortal_Report");
                        printManager.print("UltraPortal_Report", printAdapter, new PrintAttributes.Builder().build());
                    }
                }
            });
        }

        @JavascriptInterface
        public void shareWhatsApp(final String message) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        Intent intent = new Intent(Intent.ACTION_VIEW);
                        intent.setData(Uri.parse("whatsapp://send?text=" + URLEncoder.encode(message, "UTF-8")));
                        intent.setPackage("com.whatsapp");
                        activity.startActivity(intent);
                    } catch (Exception e) {
                        try {
                            Intent sendIntent = new Intent(Intent.ACTION_SEND);
                            sendIntent.setType("text/plain");
                            sendIntent.putExtra(Intent.EXTRA_TEXT, message);
                            sendIntent.setPackage("com.whatsapp");
                            activity.startActivity(sendIntent);
                        } catch (Exception ex) {
                            try {
                                Intent browserIntent = new Intent(Intent.ACTION_VIEW, Uri.parse("https://api.whatsapp.com/send?text=" + URLEncoder.encode(message, "UTF-8")));
                                activity.startActivity(browserIntent);
                            } catch (Exception ignored) {}
                        }
                    }
                }
            });
        }

        @JavascriptInterface
        public void shareApp(final String text, final String downloadUrl) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        Intent sendIntent = new Intent();
                        sendIntent.setAction(Intent.ACTION_SEND);
                        sendIntent.putExtra(Intent.EXTRA_TEXT, text);
                        sendIntent.putExtra(Intent.EXTRA_SUBJECT, "⚡ Ultra Portal — Student Workspace");
                        sendIntent.setType("text/plain");
                        Intent chooser = Intent.createChooser(sendIntent, "Share Ultra Portal via");
                        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        activity.startActivity(chooser);
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            });
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Customize system status bar & navigation bar to match #090D16
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window window = getWindow();
            window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            window.setStatusBarColor(DARK_BG_COLOR);
            window.setNavigationBarColor(DARK_BG_COLOR);
        }

        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webView);
        webView.setBackgroundColor(DARK_BG_COLOR);

        // Configure WebView Settings
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " UltraPortalApp/2.1");

        // Enable Cookies
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            cookieManager.setAcceptThirdPartyCookies(webView, true);
        }

        // Bridge native Android Print & Share capabilities
        webView.addJavascriptInterface(new WebAppInterface(this), "AndroidApp");

        // Custom WebViewClient with native intent interception
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (request != null && request.getUrl() != null) {
                    String url = request.getUrl().toString();
                    if (url.startsWith("whatsapp:") || url.startsWith("intent:") || url.startsWith("mailto:") || url.startsWith("tel:")) {
                        try {
                            Intent intent = Intent.parseUri(url, Intent.URI_INTENT_SCHEME);
                            if (intent != null) {
                                view.getContext().startActivity(intent);
                                return true;
                            }
                        } catch (Exception ignored) {}
                    }
                    if (url.contains("api.whatsapp.com") || url.contains("wa.me")) {
                        try {
                            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                            intent.setPackage("com.whatsapp");
                            view.getContext().startActivity(intent);
                            return true;
                        } catch (Exception e) {
                            try {
                                Intent genericIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                                view.getContext().startActivity(genericIntent);
                                return true;
                            } catch (Exception ignored) {}
                        }
                    }
                }
                return false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                CookieManager.getInstance().flush();
            }
        });

        webView.setWebChromeClient(new WebChromeClient());

        // Restore state or load portal
        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(PORTAL_URL);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    // Hardware Back Button Navigation
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }
}
