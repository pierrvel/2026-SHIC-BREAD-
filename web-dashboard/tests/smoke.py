"""Run against a mock-mode Vite server. Install Python playwright first."""
import os
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.getenv('BREAD_TEST_URL', 'http://127.0.0.1:5173')
executable = os.getenv('BREAD_CHROMIUM_PATH')

with sync_playwright() as p:
    browser=p.chromium.launch(**({'executable_path': executable} if executable else {}), headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.goto(BASE_URL)
    expect(page.locator('.slot-card')).to_have_count(6)
    expect(page.locator('.slot-card.stocked')).to_have_count(4)
    expect(page.locator('.slot-card.soldout')).to_have_count(2)
    page.wait_for_function('Array.from(document.querySelectorAll(".map-slot-photo img")).every(img => img.complete && img.naturalWidth > 0)')
    page.get_by_role('button',name='재고 있는 칸',exact=True).click()
    expect(page.locator('.slot-card')).to_have_count(4)
    page.get_by_role('button',name='전체 보기',exact=True).click()
    expect(page.locator('.slot-card')).to_have_count(6)
    print('PASS student stock counts, decoded WebP thumbnails and stock filter')

    page.get_by_role('button',name='관리자',exact=True).click()
    expect(page.locator('svg rect')).to_have_count(6)
    expect(page.get_by_text('원본 600 × 480px',exact=False)).to_be_visible()
    page.get_by_label('X 좌표',exact=False).fill('500')
    page.get_by_role('button',name='설정 저장하기').click()
    expect(page.get_by_role('alert')).to_contain_text('사진 바깥')
    page.get_by_label('X 좌표',exact=False).fill('50')
    page.get_by_label('칸 이름',exact=True).fill('로컬 테스트')
    page.get_by_role('slider').focus()
    page.get_by_role('slider').press('End')
    page.get_by_role('button',name='설정 저장하기').click()
    expect(page.get_by_role('status')).to_contain_text('이 브라우저에 저장')
    page.reload()
    page.get_by_role('button',name='관리자',exact=True).click()
    expect(page.get_by_label('칸 이름',exact=True)).to_have_value('로컬 테스트')
    expect(page.get_by_role('slider')).to_have_value('255')
    print('PASS out-of-bounds ROI rejection, config save and persistence')

    other=context.new_page()
    other.goto(BASE_URL)
    expect(other.locator('.slot-card.soldout')).to_have_count(6)
    other.get_by_role('button',name='관리자',exact=True).click()
    other.get_by_label('칸 이름',exact=True).fill('동시 편집 중')
    page.get_by_role('slider').fill('35')
    page.get_by_role('button',name='설정 저장하기').click()
    expect(page.get_by_role('status')).to_contain_text('이 브라우저에 저장')
    expect(other.get_by_text('새 원격 설정이 있습니다.',exact=False)).to_be_visible()
    other.get_by_role('button',name='설정 저장하기').click()
    expect(other.get_by_role('alert').filter(has_text='다른 관리자')).to_be_visible()
    expect(other.get_by_label('칸 이름',exact=True)).to_have_value('동시 편집 중')
    other.get_by_role('button',name='최신 설정 불러오기',exact=True).click()
    expect(other.get_by_label('칸 이름',exact=True)).to_have_value('로컬 테스트')
    with other.expect_download() as download:
        other.get_by_role('button',name='설정 JSON 내려받기').click()
    assert download.value.suggested_filename=='vending-config.json'
    other.get_by_role('button',name='데모 설정 초기화').click()
    expect(other.get_by_label('칸 이름',exact=True)).to_have_value('1번 칸')
    print('PASS cross-tab realtime updates, conflict protection, JSON export and reset')

    page.get_by_role('button',name='슬롯 지도',exact=True).click()
    expect(page.locator('.slot-card.stocked')).to_have_count(4)
    for width in [375,320]:
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'Overflow at {width}'
    page.get_by_role('button',name='관리자',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Admin overflow'
    print('PASS 320px/375px student and administrator layouts')
    assert not errors,errors
    browser.close()
