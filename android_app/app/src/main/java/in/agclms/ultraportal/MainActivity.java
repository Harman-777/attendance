package in.agclms.ultraportal;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.Window;
import android.view.WindowManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import java.net.URLEncoder;
import android.app.DownloadManager;
import android.os.Environment;
import android.widget.Toast;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {

    private static final String PORTAL_URL = "https://attendance-liard-three.vercel.app";
    private static final int DARK_BG_COLOR = 0xFF000000;
    private static final int LIGHT_BG_COLOR = 0xFFF4F4F5;
    private WebView webView;

    public class WebAppInterface {
        private final Activity activity;

        WebAppInterface(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public String getAppVersion() {
            return "2.7";
        }

        @JavascriptInterface
        public int getAppVersionCode() {
            return 9;
        }

        @JavascriptInterface
        public void setSystemBarTheme(final String mode) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                            Window window = activity.getWindow();
                            boolean isLight = "light".equalsIgnoreCase(mode);
                            int bgColor = isLight ? LIGHT_BG_COLOR : DARK_BG_COLOR;
                            window.setStatusBarColor(bgColor);
                            window.setNavigationBarColor(bgColor);

                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                                android.view.View decor = window.getDecorView();
                                int flags = decor.getSystemUiVisibility();
                                if (isLight) {
                                    flags |= android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                        flags |= android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                                    }
                                } else {
                                    flags &= ~android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
                                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                        flags &= ~android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                                    }
                                }
                                decor.setSystemUiVisibility(flags);
                            }
                            if (webView != null) {
                                webView.setBackgroundColor(bgColor);
                            }
                        }
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            });
        }


        @JavascriptInterface
        public void showNativeNotification(final String title, final String body) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        SharedPreferences prefs = activity.getSharedPreferences("ultra_prefs", Context.MODE_PRIVATE);
                        String notifiedKey = "notified_" + title;
                        if (prefs.getBoolean(notifiedKey, false)) {
                            return;
                        }

                        NotificationManager notificationManager = (NotificationManager) activity.getSystemService(Context.NOTIFICATION_SERVICE);
                        if (notificationManager == null) return;

                        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(PORTAL_URL + "/download/Krono.apk"));
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        PendingIntent pendingIntent = PendingIntent.getActivity(
                            activity,
                            0,
                            intent,
                            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
                        );

                        Notification.Builder builder;
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                            builder = new Notification.Builder(activity, "krono_updates");
                        } else {
                            builder = new Notification.Builder(activity);
                        }

                        builder.setSmallIcon(R.mipmap.ic_launcher)
                               .setContentTitle(title)
                               .setContentText(body)
                               .setAutoCancel(true)
                               .setContentIntent(pendingIntent);

                        notificationManager.notify(1001, builder.build());
                        prefs.edit().putBoolean(notifiedKey, true).apply();
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            });
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
                        sendIntent.putExtra(Intent.EXTRA_SUBJECT, "⚡ Krono — Student Workspace");
                        sendIntent.setType("text/plain");
                        Intent chooser = Intent.createChooser(sendIntent, "Share Krono via");
                        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        activity.startActivity(chooser);
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            });
        }

        @JavascriptInterface
        public void downloadUpdate(final String url) {
            startDownload(url);
        }

        @JavascriptInterface
        public void reloadPortal() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (webView != null) {
                        webView.clearCache(true);
                        webView.reload();
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

        // Create high-importance NotificationChannel for Ultra Portal Updates (Android 8.0+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                "krono_updates",
                "Krono Updates",
                NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Notifications about new Krono updates and features");
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }

        // On Android 13+ (API 33+), request POST_NOTIFICATIONS permission if not granted
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 101);
            }
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
        settings.setUserAgentString(settings.getUserAgentString() + " UltraPortalApp/2.4");

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
                    if (url.contains("/download/") || url.endsWith(".apk")) {
                        startDownload(url);
                        return true;
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

        // Set native DownloadListener to handle all file downloads via system download manager
        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimetype, long contentLength) {
                startDownload(url);
            }
        });

        webView.setWebChromeClient(new WebChromeClient());

        // Restore state or load portal
        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            Uri launchUri = getIntent() != null ? getIntent().getData() : null;
            if (launchUri != null && launchUri.getPath() != null && (launchUri.getPath().contains("/download/") || launchUri.getPath().endsWith(".apk"))) {
                startDownload(launchUri.toString());
                webView.loadUrl(PORTAL_URL);
            } else {
                webView.loadUrl(PORTAL_URL);
            }
        }
    }

    public void startDownload(final String url) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                    if (dm != null) {
                        Uri downloadUri = Uri.parse(url);
                        DownloadManager.Request request = new DownloadManager.Request(downloadUri);
                        request.setTitle("Krono APK Update");
                        request.setDescription("Downloading latest Krono.apk...");
                        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                        request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "Krono.apk");
                        request.setMimeType("application/vnd.android.package-archive");
                        dm.enqueue(request);

                        Toast.makeText(MainActivity.this, "⬇️ Downloading update... Check notification bar.", Toast.LENGTH_LONG).show();
                        return;
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }

                try {
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    Intent chooser = Intent.createChooser(intent, "Download Krono with");
                    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(chooser);
                } catch (Exception ex) {
                    ex.printStackTrace();
                }
            }
        });
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent != null && intent.getData() != null) {
            String path = intent.getData().getPath() != null ? intent.getData().getPath() : "";
            if (path.contains("/download/") || path.endsWith(".apk")) {
                startDownload(intent.getData().toString());
            }
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        CookieManager.getInstance().flush();
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
