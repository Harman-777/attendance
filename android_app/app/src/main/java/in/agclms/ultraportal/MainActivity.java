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
import android.provider.Settings;
import java.io.File;
import java.io.InputStream;
import java.io.FileOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import android.content.BroadcastReceiver;
import android.content.IntentFilter;
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
import android.view.View;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Button;
import android.view.animation.Animation;
import android.view.animation.AnimationUtils;
import android.os.Handler;
import android.os.Looper;

public class MainActivity extends Activity {
    private static final String PORTAL_URL = "https://attendance-liard-three.vercel.app";
    private static final int DARK_BG_COLOR = 0xFF090B0E;
    private static final int LIGHT_BG_COLOR = 0xFFE4E8EE;
    private WebView webView;
    private View splashOverlay;
    private ImageView splashLogo;
    private ProgressBar splashProgress;
    private TextView splashStatus;
    private Button btnSplashRetry;
    private boolean isSplashDismissed = false;
    private long launchTimestamp = 0;

    private BroadcastReceiver downloadCompleteReceiver = new BroadcastReceiver() {

        @Override

        public void onReceive(Context context, Intent intent) {
            String action = intent != null ? intent.getAction() : null;
            if (DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(action)) {
                try {
                    File cacheApk = new File(getCacheDir(), "Krono_update.apk");
                    if (cacheApk.exists() && cacheApk.length() > 10000) {
                        installApk(cacheApk);
                        return;
                    }
                    long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
                    if (id != -1) {
                        DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                        if (dm != null) {
                            Uri downloadedUri = dm.getUriForDownloadedFile(id);
                            if (downloadedUri != null) {
                                Intent installIntent = new Intent(Intent.ACTION_VIEW);
                                installIntent.setDataAndType(downloadedUri, "application/vnd.android.package-archive");
                                installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                                startActivity(installIntent);
                            }
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
    };

    public class WebAppInterface {
        private final Activity activity;
        WebAppInterface(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public String getAppVersion() {
            return "3.1";
        }

        @JavascriptInterface
        public int getAppVersionCode() {
            return 13;
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
                        sendIntent.putExtra(Intent.EXTRA_SUBJECT, "Krono — Student Workspace");
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
        public void openExternalBrowser(final String url) {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    openInSystemBrowser(url);
                }
            });
        }

        @JavascriptInterface
        public void installDownloadedUpdate() {
            activity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    installDownloadedApk();
                }
            });
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

    private void dismissSplash() {
        if (isSplashDismissed || splashOverlay == null) return;
        isSplashDismissed = true;
        long elapsed = System.currentTimeMillis() - launchTimestamp;
        long minDuration = 1400;
        long delay = Math.max(0, minDuration - elapsed);
        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {

            @Override

            public void run() {
                if (splashOverlay != null && splashOverlay.getVisibility() == View.VISIBLE) {
                    splashOverlay.animate()
                        .alpha(0f)
                        .setDuration(350)
                        .withEndAction(new Runnable() {

                            @Override

                            public void run() {
                                if (splashOverlay != null) {
                                    splashOverlay.setVisibility(View.GONE);
                                    if (splashLogo != null) {
                                        splashLogo.clearAnimation();
                                    }
                                }
                            }
                        })
                        .start();
                }
            }
        }, delay);
    }

    private void showSplashRetry(final String message) {
        if (isSplashDismissed) return;
        runOnUiThread(new Runnable() {

            @Override

            public void run() {
                if (splashProgress != null) splashProgress.setVisibility(View.GONE);
                if (splashStatus != null) splashStatus.setText(message);
                if (btnSplashRetry != null) btnSplashRetry.setVisibility(View.VISIBLE);
            }
        });
    }

    public void openInSystemBrowser(String url) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addCategory(Intent.CATEGORY_BROWSABLE);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        } catch (Exception e) {
            try {
                Intent chooser = Intent.createChooser(new Intent(Intent.ACTION_VIEW, Uri.parse(url)), "Open with");
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(chooser);
            } catch (Exception ignored) {}
        }
    }
    @SuppressLint("SetJavaScriptEnabled")

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        launchTimestamp = System.currentTimeMillis();
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                registerReceiver(downloadCompleteReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), 2);
            } else {
                registerReceiver(downloadCompleteReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));
            }
        } catch (Exception ignored) {}
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
        splashOverlay = findViewById(R.id.splashOverlay);
        splashLogo = findViewById(R.id.splashLogo);
        splashProgress = findViewById(R.id.splashProgress);
        splashStatus = findViewById(R.id.splashStatus);
        btnSplashRetry = findViewById(R.id.btnSplashRetry);
        if (splashLogo != null) {
            Animation pulse = AnimationUtils.loadAnimation(this, R.anim.krono_pulse);
            splashLogo.startAnimation(pulse);
        }
        if (btnSplashRetry != null) {
            btnSplashRetry.setOnClickListener(new View.OnClickListener() {

                @Override

                public void onClick(View v) {
                    btnSplashRetry.setVisibility(View.GONE);
                    if (splashProgress != null) splashProgress.setVisibility(View.VISIBLE);
                    if (splashStatus != null) splashStatus.setText("Connecting to Krono…");
                    if (webView != null) webView.reload();
                }
            });
        }
        // Subtitle dynamic pulse
        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {

            @Override

            public void run() {
                if (!isSplashDismissed && splashStatus != null) {
                    splashStatus.setText("Syncing student workspace…");
                }
            }
        }, 3000);
        // Fallback retry button if network takes > 10 seconds
        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {

            @Override

            public void run() {
                if (!isSplashDismissed) {
                    showSplashRetry("Slow connection. Tap below to retry or wait.");
                }
            }
        }, 10000);
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
        settings.setUserAgentString(settings.getUserAgentString() + " KronoApp/3.1");
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
                    // External links (e.g. github.com) must open in external system browser
                    Uri parsedUri = request.getUrl();
                    String host = parsedUri != null ? parsedUri.getHost() : null;
                    if (host != null && !host.contains("vercel.app") && !host.contains("attendance")) {
                        openInSystemBrowser(url);
                        return true;
                    }
                    if (url.contains("/download/") || url.endsWith(".apk")) {
                        startDownload(url);
                        return true;
                    }
                }
                return false;
            }

            @Override

            public void onPageCommitVisible(WebView view, String url) {
                super.onPageCommitVisible(view, url);
                dismissSplash();
            }

            @Override

            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                CookieManager.getInstance().flush();
                dismissSplash();
            }

            @Override

            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                super.onReceivedError(view, errorCode, description, failingUrl);
                showSplashRetry("Could not connect to Krono. Check internet connection.");
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
            webView.loadUrl(PORTAL_URL);
            handleIncomingIntent(getIntent());
        }
    }

    private void installApk(File apkFile) {
        if (apkFile == null || !apkFile.exists() || apkFile.length() < 10000) {
            Toast.makeText(MainActivity.this, "Update package incomplete. Please retry.", Toast.LENGTH_SHORT).show();
            return;
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                if (!getPackageManager().canRequestPackageInstalls()) {
                    Toast.makeText(MainActivity.this, "Please allow Krono to install update", Toast.LENGTH_LONG).show();
                    Intent permissionIntent = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
                    permissionIntent.setData(Uri.parse("package:" + getPackageName()));
                    permissionIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(permissionIntent);
                    return;
                }
            }
            Intent installIntent = new Intent(Intent.ACTION_VIEW);
            Uri contentUri = Uri.parse("content://" + GenericFileProvider.AUTHORITY + "/Krono_update.apk");
            installIntent.setDataAndType(contentUri, "application/vnd.android.package-archive");
            installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            installIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            installIntent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);

            java.util.List<android.content.pm.ResolveInfo> resolveInfoList = getPackageManager().queryIntentActivities(installIntent, PackageManager.MATCH_DEFAULT_ONLY);
            for (android.content.pm.ResolveInfo resolveInfo : resolveInfoList) {
                String packageName = resolveInfo.activityInfo.packageName;
                grantUriPermission(packageName, contentUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            }

            startActivity(installIntent);
        } catch (Exception e) {
            e.printStackTrace();
            Toast.makeText(MainActivity.this, "Launching installer failed: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    public void startDownload(final String url) {
        runOnUiThread(new Runnable() {

            @Override

            public void run() {
                Toast.makeText(MainActivity.this, "Downloading Krono update...", Toast.LENGTH_SHORT).show();
            }
        });
        new Thread(new Runnable() {

            @Override

            public void run() {
                boolean fastSuccess = false;
                HttpURLConnection conn = null;
                InputStream in = null;
                FileOutputStream out = null;
                try {
                    String currentUrl = url;
                    for (int r = 0; r < 4; r++) {
                        URL u = new URL(currentUrl);
                        conn = (HttpURLConnection) u.openConnection();
                        conn.setInstanceFollowRedirects(true);
                        conn.setConnectTimeout(15000);
                        conn.setReadTimeout(20000);
                        conn.setRequestProperty("User-Agent", "Mozilla/5.0 KronoApp/3.1");
                        conn.connect();
                        int code = conn.getResponseCode();
                        if (code >= 300 && code < 400) {
                            String loc = conn.getHeaderField("Location");
                            if (loc != null && !loc.isEmpty()) {
                                currentUrl = loc;
                                conn.disconnect();
                                continue;
                            }
                        }
                        break;
                    }
                    if (conn != null && conn.getResponseCode() == HttpURLConnection.HTTP_OK) {
                        File cacheApk = new File(getCacheDir(), "Krono_update.apk");
                        in = conn.getInputStream();
                        out = new FileOutputStream(cacheApk);
                        byte[] buffer = new byte[8192];
                        int bytesRead;
                        while ((bytesRead = in.read(buffer)) != -1) {
                            out.write(buffer, 0, bytesRead);
                        }
                        out.flush();
                        if (cacheApk.exists() && cacheApk.length() > 10000) {
                            fastSuccess = true;
                            runOnUiThread(new Runnable() {

                                @Override

                                public void run() {
                                    Toast.makeText(MainActivity.this, "Download complete! Opening installer...", Toast.LENGTH_SHORT).show();
                                    if (webView != null) {
                                        webView.evaluateJavascript("if (window.onKronoDownloadComplete) window.onKronoDownloadComplete();", null);
                                    }
                                    installApk(new File(getCacheDir(), "Krono_update.apk"));
                                }
                            });
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                } finally {
                    try { if (in != null) in.close(); } catch (Exception ignored) {}
                    try { if (out != null) out.close(); } catch (Exception ignored) {}
                    try { if (conn != null) conn.disconnect(); } catch (Exception ignored) {}
                }
                if (!fastSuccess) {
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
                                    Toast.makeText(MainActivity.this, "Downloading in background... Check notification bar.", Toast.LENGTH_LONG).show();
                                    return;
                                }
                            } catch (Exception ex) {
                                ex.printStackTrace();
                            }
                            try {
                                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                Intent chooser = Intent.createChooser(intent, "Download Krono with");
                                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                startActivity(chooser);
                            } catch (Exception ignored) {}
                        }
                    });
                }
            }
        }).start();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try {
            unregisterReceiver(downloadCompleteReceiver);
        } catch (Exception ignored) {}
    }

    public void installDownloadedApk() {
        File cacheApk = new File(getCacheDir(), "Krono_update.apk");
        if (cacheApk.exists() && cacheApk.length() > 10000) {
            installApk(cacheApk);
            return;
        }

        File extApk = new File(getExternalFilesDir(null), "Krono_update.apk");
        if (extApk.exists() && extApk.length() > 10000) {
            installApk(extApk);
            return;
        }

        File publicApk = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "Krono.apk");
        if (publicApk.exists() && publicApk.length() > 10000) {
            installApk(publicApk);
            return;
        }

        // Query DownloadManager for any completed download
        try {
            DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
            if (dm != null) {
                DownloadManager.Query query = new DownloadManager.Query();
                query.setFilterByStatus(DownloadManager.STATUS_SUCCESSFUL);
                android.database.Cursor c = dm.query(query);
                if (c != null) {
                    try {
                        while (c.moveToNext()) {
                            int titleIdx = c.getColumnIndex(DownloadManager.COLUMN_TITLE);
                            int uriIdx = c.getColumnIndex(DownloadManager.COLUMN_LOCAL_URI);
                            if (titleIdx != -1 && uriIdx != -1) {
                                String title = c.getString(titleIdx);
                                String localUri = c.getString(uriIdx);
                                if (title != null && (title.contains("Krono") || title.contains("UltraPortal")) && localUri != null) {
                                    Intent installIntent = new Intent(Intent.ACTION_VIEW);
                                    installIntent.setDataAndType(Uri.parse(localUri), "application/vnd.android.package-archive");
                                    installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                                    startActivity(installIntent);
                                    return;
                                }
                            }
                        }
                    } finally {
                        c.close();
                    }
                }
            }
        } catch (Exception ignored) {}

        Toast.makeText(MainActivity.this, "Downloading latest update...", Toast.LENGTH_SHORT).show();
        startDownload(PORTAL_URL + "/download/Krono.apk");
    }

    private void handleIncomingIntent(Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();

        // Notification Click: User tapped "Download complete" in Android notification shade
        if (DownloadManager.ACTION_NOTIFICATION_CLICKED.equals(action)) {
            installDownloadedApk();
            return;
        }

        Uri launchUri = intent.getData();
        if (launchUri != null && launchUri.getPath() != null) {
            String path = launchUri.getPath();
            if (path.contains("/download/") || path.endsWith(".apk")) {
                File cacheApk = new File(getCacheDir(), "Krono_update.apk");
                if (cacheApk.exists() && cacheApk.length() > 10000) {
                    installApk(cacheApk);
                    return;
                }
                startDownload(launchUri.toString());
            }
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingIntent(intent);
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
