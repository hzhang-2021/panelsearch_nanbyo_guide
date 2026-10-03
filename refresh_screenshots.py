from pathlib import Path
from urllib.parse import urlparse, urlencode
import json, re, sys, time, datetime
from playwright.sync_api import sync_playwright
import yaml

ROOT = Path(r'G:\visualstudio_code_workspace\pubcasefinder_pcf')
OUT = Path(__file__).parent / 'captures'
OUT.mkdir(exist_ok=True)
cfg = yaml.safe_load((ROOT/'tests/e2e_psn/config/ja/config.yaml').read_text(encoding='utf-8'))
origin = cfg['settings']['origin']
manifest=[]
blocked=[]
# These POST endpoints only load data. All other writes are prevented during capture.
READ_POST={'/panelsearch_nanbyo_admin_load_user','/panelsearch_nanbyo_admin_load_activity',
 '/panelsearch_nanbyo_admin_load_activity_detail','/panelsearch_nanbyo_admin_load_activity_history',
 '/panelsearch_nanbyo_admin_load_authentication_log'}
def guard(route):
    req=route.request
    if req.method not in ('GET','HEAD','OPTIONS') and urlparse(req.url).path not in READ_POST:
        blocked.append({'method':req.method,'path':urlparse(req.url).path})
        route.abort()
    else: route.continue_()
def wait(page):
    for s in ('#vgp-loader-whole','#vgp-loader','#fh5co-loader','#compare-loader'):
        for el in page.locator(s).all():
            try: el.wait_for(state='hidden',timeout=45000)
            except Exception: pass
    try: page.wait_for_load_state('networkidle',timeout=18000)
    except Exception: pass
def shot(page,key,role,caption):
    wait(page)
    name=key+'.png'
    page.screenshot(path=str(OUT/name),full_page=False,mask=[page.locator('input[type="password"]')])
    manifest.append({'key':key,'file':name,'role':role,'caption':caption,'url':page.url,
        'date':datetime.datetime.now().astimezone().isoformat(),'source':'今回取得','status':'captured'})
    print('CAPTURE '+key,flush=True)
def clickshot(page,sel,key,role,caption):
    loc=page.locator(sel).first
    if loc.count() and loc.is_visible():
        loc.click(timeout=10000); shot(page,key,role,caption); return True
    manifest.append({'key':key,'role':role,'status':'unavailable','caption':caption})
    return False
def record_error(key,e):
    # Keep secrets and response bodies out of logs.
    manifest.append({'key':key,'status':'error','error':type(e).__name__})
    print('ERROR '+key+' '+type(e).__name__,flush=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    contexts={}
    for role,state in [('anonymous',None),('reviewer','member.json'),('curator','curator.json'),('admin','admin.json')]:
        opts={'viewport':{'width':1600,'height':1000},'accept_downloads':True}
        if state: opts['storage_state']=str(ROOT/'tests/e2e_psn/playwright/.auth'/state)
        ctx=browser.new_context(**opts);ctx.route('**/*',guard);contexts[role]=ctx
    for name,settings in cfg['pages'].items():
        role=settings['role'];page=contexts[role].new_page()
        try:
            page.goto(origin+settings['path']+'?'+urlencode({**settings.get('query',{}),'lang':'ja'}),wait_until='domcontentloaded',timeout=60000)
            wait(page)
            if urlparse(page.url).path != settings['path']: raise RuntimeError('redirected')
            for sel in settings['visible']:page.locator(sel).wait_for(state='visible',timeout=30000)
            shot(page,name,role,name+' 初期画面')
            if name=='panel_list':
                clickshot(page,'#nav-login','login',role,'Log in と Sign up')
                page.reload();wait(page)
                page.locator('#btn-vgp-target').click()
                page.get_by_role('button',name='Gene',exact=True).click()
                page.locator('#vgp-filter').fill('ACTA1');page.wait_for_timeout(1600)
                shot(page,'panel_list_gene_search',role,'Gene モードで ACTA1 を検索')
                page.locator('#vgp-filter').fill('');page.wait_for_timeout(1200)
                # Expand actual nonempty rows without changing data.
                for kind,selector in [('genes','.vgp-summary-controll'),('features','.vgp-summary-controll')]:
                    candidates=page.locator(selector).all()
                    for c in candidates:
                        if c.is_visible() and ((kind=='genes' and 'gene' in (c.get_attribute('data-table-id') or '')) or (kind=='features' and 'phenotype' in (c.get_attribute('data-table-id') or ''))):
                            c.click();shot(page,'panel_list_'+kind,role,kind+' 展開');break
            elif name=='panel_detail':
                for sel,label in [('#nav-vgp-version-comments-panel','version_comments'),('#nav-vgp-reviewers-panel','reviewers'),('#nav-vgp-compare-panel','comparison')]:
                    clickshot(page,sel,'panel_detail_'+label,role,label)
                page.locator('#nav-vgp-panel-genes-panel').click()
                page.locator('#vgp-panel-genes-filter').fill('ACTA1')
                shot(page,'panel_detail_filter',role,'ACTA1 のエンティティ絞り込み')
                for sel,label in [('.vgp-summary-controll.paper','papers'),('.vgp-summary-controll[id$="-reviewer"]','reviewer_ratings'),('.vgp-summary-controll[id$="-reference"]','reference_ratings')]:
                    try:clickshot(page,sel,'panel_detail_'+label,role,label)
                    except Exception as e:record_error('panel_detail_'+label,e)
            elif name=='panel_entity_detail':
                clickshot(page,'#nav-vgp-history-panel','entity_history',role,'History')
                clickshot(page,'#nav-vgp-panel-gene-review-panel','entity_reviews',role,'Review')
                clickshot(page,'#btn_show_more_info','entity_more_info',role,'遺伝子の追加情報')
            elif name=='admin_profile':
                clickshot(page,'#vgp-user-btn-edit','profile_edit',role,'プロフィール編集')
            elif name=='admin_user':
                clickshot(page,'#user-table .name','user_detail',role,'ユーザー詳細')
                clickshot(page,'#vgp-user-btn-edit','user_edit',role,'ユーザー編集')
            elif name=='admin_group':
                clickshot(page,'#group_list_table tbody tr .group-title','group_members',role,'グループメンバー')
                clickshot(page,'#nav-group-disease','group_panels',role,'グループの疾患登録')
            elif name=='admin_activity':
                clickshot(page,'#activity_table tbody tr','activity_detail',role,'活動の変更前後')
            elif name=='admin_incharge':
                clickshot(page,'#activity_table tbody tr','incharge_detail',role,'担当活動の履歴と確認操作')
            elif name=='admin_mail':
                clickshot(page,'#btn_load_email','mail_logs',role,'メールログ読込')
                clickshot(page,'#nav-template-panel','mail_template',role,'メールテンプレート')
                clickshot(page,'#btn_template_modify','mail_template_edit',role,'テンプレート編集')
                page.locator('#btn_template_cancel').click()
                clickshot(page,'#nav-smtp-panel','mail_smtp',role,'SMTP 設定 閲覧専用')
            elif name=='ontology':
                clickshot(page,'#ontology-list-table tbody tr','ontology_selected',role,'DB 版の選択')
                clickshot(page,'#btn_load_selected_ttl_db','ontology_db_tree',role,'DB 版の読込')
                clickshot(page,'#nav-ontology-upload-panel','ontology_file',role,'TTL ファイルの分析')
                page.locator('#ttlFile').set_input_files(str(ROOT/'tests/e2e_psn/test_data/nando_test_20260714.ttl'))
                shot(page,'ontology_analysis',role,'TTL のブラウザー内分析 保存前')
        except Exception as e:record_error(name,e)
        finally:page.close();(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # Role-specific review and definition panels, without submitting.
    for role in ('reviewer','curator','admin'):
        page=contexts[role].new_page()
        try:
            settings=cfg['pages']['panel_detail']
            page.goto(origin+settings['path']+'?'+urlencode({**settings['query'],'lang':'ja'}),wait_until='domcontentloaded')
            shot(page,'panel_detail_'+role,role,'パネル詳細 '+role)
            clickshot(page,'.vgp-add-review-btn[data-gene_symbol="ACTA1"]','review_form_'+role,role,'Add Review 入力 '+role)
            settings=cfg['pages']['panel_entity_detail']
            page.goto(origin+settings['path']+'?'+urlencode({**settings['query'],'lang':'ja'}),wait_until='domcontentloaded')
            shot(page,'entity_'+role,role,'Review と Definition の権限 '+role)
            if role in ('curator','admin'):clickshot(page,'#btn-definition-edit','definition_edit_'+role,role,'Entity Definition 編集 '+role)
        except Exception as e:record_error('role_'+role,e)
        finally:page.close()
    browser.close()
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'blocked.json').write_text(json.dumps(blocked,indent=2),encoding='utf-8')
print('DONE captures='+str(sum(x['status']=='captured' for x in manifest))+' blocked_writes='+str(len(blocked)),flush=True)
