"""End-to-end local runtime test. Use a disposable --sample server/data folder."""
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

base = os.environ['BREAD_TEST_URL']
data_dir = Path(os.environ['BREAD_TEST_DATA_DIR'])
password = (data_dir / 'admin-password').read_text().strip()
executable = os.getenv('BREAD_CHROMIUM_PATH')

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}), headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors, external = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: external.append(request.url) if request.url.startswith(('https:', 'http:')) and not request.url.startswith(base + '/') else None)
    page.goto(base)
    assert page.request.get(base + '/api/state').json()['meta']['sample'], 'Use a disposable SAMPLE server only'
    expect(page.locator('.slot-card')).to_have_count(6)
    expect(page.locator('.slot-card.stocked')).to_have_count(4)
    expect(page.get_by_text('파이 샘플 모드', exact=True)).to_be_visible()
    page.get_by_role('button', name='관리자', exact=True).click()
    expect(page.get_by_role('heading', name='관리자 로그인')).to_be_visible()
    page.get_by_label('비밀번호').fill('incorrect-password')
    page.get_by_role('button', name='로그인', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('비밀번호가 올바르지')
    page.get_by_label('비밀번호').fill(password)
    page.get_by_role('button', name='로그인', exact=True).click()
    expect(page.get_by_role('heading', name='자판기 설정')).to_be_visible()
    expect(page.get_by_text('원본 600 × 480px', exact=False)).to_be_visible()
    print('PASS Pi runtime renders analyzed inventory; admin authentication and camera photo work')

    student = context.new_page()
    student.goto(base)
    expect(student.locator('.slot-card.stocked')).to_have_count(4)
    page.get_by_role('slider').fill('255')
    page.get_by_role('button', name='설정 저장하기').click()
    expect(page.get_by_role('status').filter(has_text='설정이 저장')).to_be_visible()
    expect(student.locator('.slot-card.soldout')).to_have_count(6)
    assert page.request.get(base + '/api/state').json()['config']['threshold'] == 255
    print('PASS saved browser threshold reaches Python and updates another browser view')

    other = context.new_page()
    other.goto(base)
    other.get_by_role('button', name='관리자', exact=True).click()
    expect(other.get_by_label('칸 이름')).to_be_visible()
    other.get_by_label('칸 이름').fill('충돌 테스트')
    page.get_by_role('slider').fill('35')
    page.get_by_role('button', name='설정 저장하기').click()
    expect(student.locator('.slot-card.stocked')).to_have_count(4)
    expect(other.get_by_text('새 원격 설정이 있습니다.', exact=False)).to_be_visible()
    other.get_by_role('button', name='설정 저장하기').click()
    expect(other.get_by_role('alert').filter(has_text='다른 관리자')).to_be_visible()
    expect(other.get_by_label('칸 이름')).to_have_value('충돌 테스트')
    print('PASS live cross-browser conflict protection preserves unsaved edits')

    image_path = data_dir / 'fixtures/sample_vending.jpg'
    original = image_path.read_bytes()
    try:
        image_path.write_bytes((data_dir / 'fixtures/empty_vending.jpg').read_bytes())
        page.get_by_role('button', name='지금 촬영', exact=True).click()
        expect(student.locator('.slot-card.soldout')).to_have_count(6)
        checkbox = page.get_by_role('checkbox', name='모든 칸이 비어 있음을 확인했습니다')
        calibration = page.get_by_role('button', name='현재 사진을 빈 칸 기준으로 촬영')
        expect(calibration).to_be_disabled()
        checkbox.check()
        calibration.click()
        expect(page.get_by_role('status').filter(has_text='빈 칸 기준으로 저장')).to_be_visible()
        image_path.write_bytes(original)
        page.get_by_role('button', name='지금 촬영', exact=True).click()
        expect(student.locator('.slot-card.stocked')).to_have_count(4)
    finally:
        image_path.write_bytes(original)
    print('PASS full empty-reference calibration followed by real image reanalysis')

    student.route('**/api/state', lambda route: route.abort())
    expect(student.get_by_role('alert')).to_contain_text('파이에 연결하지 못했습니다')
    student.unroute('**/api/state')
    expect(student.get_by_role('alert')).to_have_count(0)
    expect(student.locator('.slot-card.stocked')).to_have_count(4)
    student.set_viewport_size({'width': 375, 'height': 900})
    assert student.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('button', name='로그아웃', exact=True).click()
    expect(page.get_by_role('heading', name='관리자 로그인')).to_be_visible()
    assert page.request.post(base + '/api/capture', data={}).status == 401
    assert not errors, errors
    assert not external, external
    print('PASS connection recovery, mobile layout, logout enforcement and zero Firebase requests')
    browser.close()
