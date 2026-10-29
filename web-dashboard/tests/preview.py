"""Standalone Jaebbangso HTML with an opaque origin and blocked localStorage."""
import base64
import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

html = (Path(__file__).resolve().parents[2] / 'index.html').read_text()
png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aKJkAAAAASUVORK5CYII=')
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('BREAD_CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url))
    page.route('https://preview-camera.invalid/**', lambda r: r.fulfill(body=png, content_type='image/png'))
    page.set_content('<iframe id="preview" sandbox="allow-scripts" style="position:fixed;inset:0;border:0;width:100%;height:100%"></iframe>')
    page.locator('#preview').evaluate('(frame, html) => { frame.srcdoc = html; }', html)
    frame = page.frame_locator('#preview')
    expect(frame.get_by_role('heading', name='빵 남았나, 창문으로 보고 가요')).to_be_visible()
    expect(frame.locator('#glass')).to_have_attribute('data-state', 'idle')
    assert not requests, requests
    frame.locator('#shadeBtn').click()
    frame.get_by_label('MJPEG 스트리밍 HTTPS 주소').fill('https://preview-camera.invalid/?action=stream')
    frame.get_by_role('button', name='저장하고 연결').click()
    expect(frame.locator('#glass')).to_have_attribute('data-state', 'live')
    expect(frame.locator('#connectionNotice')).to_contain_text('현재 창에만')
    frame.locator('#pauseBtn').click()
    expect(frame.locator('#glass')).to_have_attribute('data-state', 'paused')
    frame.locator('[data-open-settings]').click(); frame.locator('#clearBtn').click()
    expect(frame.locator('#glass')).to_have_attribute('data-state', 'idle')
    page.set_viewport_size({'width':320,'height':900})
    assert frame.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
    assert not errors, errors
    assert all(u.startswith('https://preview-camera.invalid/') for u in requests), requests
    print('PASS portable Jaebbangso: idle without camera, real image binding, blocked storage, pause/reset, 320px layout, no bundled inventory or external dependencies')
    browser.close()
