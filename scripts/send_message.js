#!/usr/bin/env node
/**
 * send_message.js
 * 
 * Reliably sends a message to ChatGPT Web (chatgpt.com) using the Chrome DevTools Protocol.
 * Key features:
 * 1. Discovers Chrome DevTools port via DevToolsActivePort or HTTP endpoint.
 * 2. Connects over WebSocket to Chrome DevTools.
 * 3. Focuses the ChatGPT tab.
 * 4. ALWAYS refreshes the page (location.reload()) before sending to clear stale DOM/WebSockets.
 * 5. Waits for #prompt-textarea to mount and become interactive.
 * 6. Inserts text via CDP Input.insertText (avoiding clipboard or OS keystroke issues).
 * 7. Clicks the send button (or dispatches Enter key).
 * 8. Verifies message delivery in the DOM before exiting with code 0.
 */

const fs = require('fs');
const path = require('path');
const http = require('http');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Parse command-line arguments
let message = '';
let prepareOnly = false;
for (let i = 2; i < process.argv.length; i++) {
    const arg = process.argv[i];
    if (arg === '--prepare-only') {
        prepareOnly = true;
    } else if (arg === '--file' || arg === '-f') {
        const filePath = process.argv[++i];
        if (!filePath || !fs.existsSync(filePath)) {
            console.error(`Error: file not found: ${filePath}`);
            process.exit(1);
        }
        message = fs.readFileSync(filePath, 'utf-8');
    } else if (arg === '--help' || arg === '-h') {
        console.log('Usage: node send_message.js [--prepare-only] "<message>"');
        console.log('       node send_message.js [--prepare-only] --file <file_path>');
        process.exit(0);
    } else if (!message) {
        message = arg;
    }
}

if (!message || !message.trim()) {
    console.error('Usage: node send_message.js [--prepare-only] "<message>" or node send_message.js [--prepare-only] --file <file_path>');
    process.exit(1);
}

// Locate Chrome DevTools WebSocket URL
async function getBrowserWsUrl() {
    // 1. Check explicit environment variables
    if (process.env.CHROME_DEVTOOLS_WS_URL) {
        return process.env.CHROME_DEVTOOLS_WS_URL;
    }

    // 2. Candidate paths for DevToolsActivePort
    const candidatePaths = [
        process.env.CHROME_DEVTOOLS_PORT_FILE,
        path.join(process.env.HOME || '', 'Library/Application Support/Google/Chrome/DevToolsActivePort'),
        path.join(process.env.HOME || '', '.config/google-chrome/DevToolsActivePort'),
        path.join(process.env.HOME || '', '.config/chromium/DevToolsActivePort')
    ].filter(Boolean);

    for (const p of candidatePaths) {
        if (fs.existsSync(p)) {
            try {
                const lines = fs.readFileSync(p, 'utf-8').trim().split('\n');
                const port = lines[0].trim();
                const wsPath = lines[1].trim();
                return `ws://127.0.0.1:${port}${wsPath}`;
            } catch (e) {
                // Continue to next candidate
            }
        }
    }

    // 3. Fallback: Query http://127.0.0.1:<port>/json/version
    const port = process.env.CHROME_DEVTOOLS_PORT || '9222';
    try {
        const json = await new Promise((resolve, reject) => {
            const req = http.get(`http://127.0.0.1:${port}/json/version`, { timeout: 3000 }, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try { resolve(JSON.parse(data)); } catch (err) { reject(err); }
                });
            });
            req.on('error', reject);
            req.on('timeout', () => req.destroy(new Error('Connection timed out')));
        });
        if (json && json.webSocketDebuggerUrl) {
            return json.webSocketDebuggerUrl;
        }
    } catch (e) {
        // DevTools endpoint not reachable
    }

    throw new Error(
        'Could not connect to Chrome DevTools Protocol.\n' +
        'Please ensure Google Chrome is running with remote debugging enabled.\n' +
        'Options:\n' +
        '  1. Open chrome://inspect/#remote-debugging in Chrome and verify it is enabled.\n' +
        '  2. Or launch Chrome with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222\n'
    );
}

async function main() {
    console.log('=== Connecting to Chrome DevTools Protocol ===');
    const wsUrl = await getBrowserWsUrl();
    console.log(`Connecting to: ${wsUrl}`);

    const WebSocketClient = globalThis.WebSocket;
    if (!WebSocketClient) {
        throw new Error('globalThis.WebSocket is not defined. Please run with Node.js v21+ or install ws.');
    }

    const ws = new WebSocketClient(wsUrl);
    let messageId = 1;
    const callbacks = new Map();

    function send(method, params = {}, sessionId = undefined) {
        return new Promise((resolve, reject) => {
            const id = messageId++;
            callbacks.set(id, { resolve, reject });
            const msg = { id, method, params };
            if (sessionId) msg.sessionId = sessionId;
            ws.send(JSON.stringify(msg));
        });
    }

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.id && callbacks.has(data.id)) {
                const { resolve, reject } = callbacks.get(data.id);
                callbacks.delete(data.id);
                if (data.error) reject(new Error(JSON.stringify(data.error)));
                else resolve(data.result);
            }
        } catch (e) {
            console.error('WebSocket message parsing error:', e);
        }
    };

    await new Promise((resolve, reject) => {
        ws.onopen = resolve;
        ws.onerror = reject;
    });

    console.log('Connected to Chrome DevTools.');

    // 1. Locate ChatGPT tab
    const { targetInfos } = await send('Target.getTargets');
    const pages = targetInfos.filter(t => t.type === 'page');
    // Prioritize active conversation URL (/c/) over generic root
    const chatGptTarget = pages.find(p => p.url.includes('chatgpt.com/c/')) ||
                          pages.find(p => p.url.includes('chatgpt.com'));

    if (!chatGptTarget) {
        throw new Error('No ChatGPT page found among open Chrome tabs! Please open https://chatgpt.com in Chrome first.');
    }
    console.log(`Found ChatGPT tab: [${chatGptTarget.targetId}] "${chatGptTarget.title}" -> ${chatGptTarget.url}`);

    // 2. Focus and attach to the target
    await send('Target.activateTarget', { targetId: chatGptTarget.targetId });
    const attachRes = await send('Target.attachToTarget', {
        targetId: chatGptTarget.targetId,
        flatten: true
    });
    const sessionId = attachRes.sessionId;

    // 3. User Requirement: Refresh the page before sending every message
    console.log('=== Refreshing ChatGPT page prior to sending (per user instruction) ===');
    await send('Page.enable', {}, sessionId);
    await send('Runtime.evaluate', { expression: 'location.reload()' }, sessionId);

    // 4. Wait for page reload to complete and #prompt-textarea to become available
    console.log('Waiting for page reload and #prompt-textarea readiness...');
    let textareaReady = false;
    for (let i = 0; i < 35; i++) {
        await sleep(1000);
        try {
            const res = await send('Runtime.evaluate', {
                expression: `
                    (() => {
                        const el = document.querySelector('#prompt-textarea');
                        if (!el) return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    })()
                `,
                returnByValue: true
            }, sessionId);
            if (res && res.result && res.result.value === true) {
                textareaReady = true;
                break;
            }
        } catch (e) {
            // Execution context may be refreshing; ignore and retry
        }
    }

    if (!textareaReady) {
        throw new Error('Timed out waiting for #prompt-textarea after page reload! Check if ChatGPT is stuck or asking for login/verification.');
    }
    console.log('#prompt-textarea is ready.');
    await sleep(600);

    // 5. Focus #prompt-textarea and clear any residual draft
    await send('Runtime.evaluate', {
        expression: `
            (() => {
                const el = document.querySelector('#prompt-textarea');
                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                el.focus();
                el.innerHTML = '';
                el.dispatchEvent(new Event('input', { bubbles: true }));
            })()
        `,
        returnByValue: true
    }, sessionId);

    // 6. Insert message content via Input.insertText (native CDP text input)
    console.log('=== Inserting message payload ===');
    await send('Input.insertText', { text: message.trim() }, sessionId);
    await sleep(800);

    if (prepareOnly) {
        console.log('>>> PREPARED: Message inserted; send button intentionally not clicked. <<<');
        ws.close();
        process.exit(0);
    }

    // 7. Click send button or dispatch Enter
    console.log('=== Submitting message ===');
    const submitRes = await send('Runtime.evaluate', {
        expression: `
            (() => {
                const sendBtn = document.querySelector('button[data-testid="send-button"]') ||
                                document.querySelector('#composer-submit-button') ||
                                document.querySelector('button[aria-label="Send prompt"]') ||
                                document.querySelector('button[aria-label="Send message"]');
                if (sendBtn && !sendBtn.disabled) {
                    sendBtn.click();
                    return { clicked: true, method: 'button' };
                }
                return { clicked: false };
            })()
        `,
        returnByValue: true
    }, sessionId);

    if (!submitRes.result.value.clicked) {
        console.log('Send button not directly clickable, dispatching Enter key...');
        await send('Input.dispatchKeyEvent', {
            type: 'rawKeyDown',
            key: 'Enter',
            code: 'Enter',
            windowsVirtualKeyCode: 13
        }, sessionId);
        await send('Input.dispatchKeyEvent', {
            type: 'keyUp',
            key: 'Enter',
            code: 'Enter',
            windowsVirtualKeyCode: 13
        }, sessionId);
    } else {
        console.log('Clicked send button directly.');
    }

    // 8. Verify message submission in DOM
    console.log('=== Verifying message delivery ===');
    const snippet = message.trim().slice(0, 30);
    let verified = false;
    for (let attempt = 1; attempt <= 20; attempt++) {
        await sleep(1000);
        try {
            const check = await send('Runtime.evaluate', {
                expression: `
                    (() => {
                        const el = document.querySelector('#prompt-textarea');
                        const userMessages = Array.from(document.querySelectorAll('[data-message-author-role="user"]'));
                        const lastUserMsg = userMessages.length > 0 ? userMessages[userMessages.length - 1].innerText : '';
                        const stopBtn = document.querySelector('button[data-testid="stop-button"]') ||
                                        document.querySelector('button[aria-label="Stop streaming"]') ||
                                        document.querySelector('button[aria-label="Stop generating"]');
                        return {
                            textareaEmpty: !el || el.innerText.trim() === '',
                            userMessagesCount: userMessages.length,
                            containsSnippet: lastUserMsg.includes(${JSON.stringify(snippet)}),
                            isStreaming: !!stopBtn
                        };
                    })()
                `,
                returnByValue: true
            }, sessionId);

            const status = check.result.value;
            console.log(`[Verification attempt ${attempt}/20]:`, status);
            if (status.containsSnippet || (status.textareaEmpty && status.isStreaming)) {
                verified = true;
                break;
            }
        } catch (e) {
            // Ignore temporary DOM evaluation exceptions
        }
    }

    if (!verified) {
        throw new Error('Message submission could not be verified in DOM within timeout!');
    }

    console.log('>>> SUCCESS: Message sent and confirmed in ChatGPT conversation! <<<');
    ws.close();
    process.exit(0);
}

main().catch(err => {
    console.error('Fatal error in send_message.js:', err.message || err);
    process.exit(1);
});
