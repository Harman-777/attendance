self.addEventListener("install", function (event) {
    self.skipWaiting();
});

self.addEventListener("activate", function (event) {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", function (event) {
    let payload = {
        title: "⚠️ Ultra Portal Attendance Alert",
        body: "New attendance update detected on your portal account.",
        url: "/dashboard"
    };

    if (event.data) {
        try {
            payload = Object.assign(payload, event.data.json());
        } catch (e) {
            payload.body = event.data.text();
        }
    }

    const options = {
        body: payload.body,
        icon: "/static/icons/icon-192.png",
        badge: "/static/icons/icon-192.png",
        vibrate: [200, 100, 200],
        data: { url: payload.url || "/dashboard" },
        actions: [
            { action: "open", title: "View & Dispute" }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(payload.title, options)
    );
});

self.addEventListener("notificationclick", function (event) {
    event.notification.close();
    const targetUrl = (event.notification.data && event.notification.data.url) || "/dashboard";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clientList) {
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url.indexOf(targetUrl) !== -1 && "focus" in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});