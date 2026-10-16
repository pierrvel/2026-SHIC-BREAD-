"""Verify portable HTML with no server, storage access or native form submission."""
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

root = Path(__file__).resolve().parents[2]
html = (root / 'index.html').read_text(encoding='utf-8')
executable = os.getenv('BREAD_CHROMIUM_PATH')

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}), headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors, requests = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append(request.url))
    page.set_content('<iframe id="preview" title="대시보드 미리보기" sandbox="allow-scripts allow-downloads" style="position:fixed;inset:0;border:0;width:100%;height:100%"></iframe>')
    page.locator('#preview').evaluate('(frame, html) => { frame.srcdoc = html; }', html)
    frame = page.frame_locator('#preview')
    expect(frame.locator('.slot-card')).to_have_count(6)
    expect(frame.locator('.slot-card.stocked')).to_have_count(4)
    expect(frame.locator('.slot-card.soldout')).to_have_count(2)
    frame.get_by_role('button', name='재고 있는 칸', exact=True).click()
    expect(frame.locator('.slot-card')).to_have_count(4)
    print('PASS standalone HTML renders student inventory and filter without a server')

    frame.get_by_role('button', name='관리자', exact=True).click()
    expect(frame.locator('svg rect')).to_have_count(6)
    expect(frame.get_by_text('원본 600 × 480px', exact=False)).to_be_visible()
    assert frame.locator('.roi-preview img').evaluate('image => image.complete && image.naturalWidth === 600')
    frame.get_by_role('slider').fill('255')
    frame.get_by_role('button', name='설정 저장하기').click()
    expect(frame.get_by_role('status')).to_contain_text('이 미리보기에 적용')
    expect(frame.get_by_role('status')).to_contain_text('창을 닫으면 초기화')
    frame.get_by_role('button', name='재고 확인', exact=True).click()
    expect(frame.locator('.slot-card.soldout')).to_have_count(6)
    frame.get_by_role('button', name='관리자', exact=True).click()
    frame.get_by_role('button', name='데모 설정 초기화').click()
    expect(frame.get_by_role('slider')).to_have_value('35')
    print('PASS embedded administrator photo, in-memory settings and reset with storage denied')

    frame.get_by_role('button', name='재고 확인', exact=True).click()
    expect(frame.locator('.slot-card.stocked')).to_have_count(4)
    page.set_viewport_size({'width': 375, 'height': 900})
    assert frame.locator('html').evaluate('html => html.scrollWidth <= window.innerWidth')
    assert not errors, errors
    assert not [url for url in requests if url.startswith(('http:', 'https:'))], requests
    print('PASS mobile preview, no JavaScript errors, no external resource requests')
    browser.close()
