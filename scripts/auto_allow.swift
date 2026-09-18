import Cocoa
import ApplicationServices

/**
 * auto_allow.swift
 *
 * Lightweight daemon that automatically detects and clicks the "Allow" button
 * on Google Chrome's "Allow remote debugging?" security prompt using macOS Accessibility API.
 *
 * Modern Chrome (136+) shows:
 * "Allow remote debugging? An external app wants full control over this Chrome session..."
 *
 * This daemon runs in the background and approves the dialog within 500ms, eliminating
 * manual clicks and popup interruptions.
 */

var lastPressTime: TimeInterval = 0

func findAndPressAllow(_ el: AXUIElement) -> Bool {
    let now = Date().timeIntervalSince1970
    // Cooldown of 1 second to avoid multi-press jitter
    if now - lastPressTime < 1.0 { return false }
    
    var roleRef: CFTypeRef?
    var titleRef: CFTypeRef?
    AXUIElementCopyAttributeValue(el, kAXRoleAttribute as CFString, &roleRef)
    AXUIElementCopyAttributeValue(el, kAXTitleAttribute as CFString, &titleRef)
    
    if (roleRef as? String) == "AXButton" && (titleRef as? String) == "Allow" {
        let err = AXUIElementPerformAction(el, kAXPressAction as CFString)
        if err == .success {
            lastPressTime = now
            print("[\(Date())] Auto-approved Chrome remote debugging prompt.")
            return true
        }
    }
    
    var kidsRef: CFTypeRef?
    AXUIElementCopyAttributeValue(el, kAXChildrenAttribute as CFString, &kidsRef)
    if let kids = kidsRef as? [AXUIElement] {
        for kid in kids {
            if findAndPressAllow(kid) { return true }
        }
    }
    return false
}

func checkOnce() {
    guard let chrome = NSRunningApplication.runningApplications(withBundleIdentifier: "com.google.Chrome").first else { return }
    let app = AXUIElementCreateApplication(chrome.processIdentifier)
    var wRef: CFTypeRef?
    AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &wRef)
    guard let windows = wRef as? [AXUIElement] else { return }
    
    for w in windows {
        if findAndPressAllow(w) { break }
    }
}

// Check every 500ms
while true {
    checkOnce()
    Thread.sleep(forTimeInterval: 0.5)
}
