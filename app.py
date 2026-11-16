"""InvoisLah — Python-first Malaysian invoice management prototype.

Run with: streamlit run app.py
This app manages local invoices; it does not connect to LHDN/MyInvois.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import csv
from html import escape
from io import StringIO
import sqlite3

import pandas as pd
import streamlit as st

from data_store import (
    init_db, get_profile, save_profile, suggest_invoice_number,
    save_invoice, get_invoice, list_invoices, set_status, effective_status,
    delete_invoice, save_attachment, list_attachments, delete_attachment, attachment_bytes,
    save_business_logo, get_business_logo,
)
from invoice_logic import CURRENCIES, ID_TYPES, TAX_TYPES, fmt, money, totals, validate_invoice
from pdf_export import invoice_pdf
from style import apply_theme

st.set_page_config(page_title='InvoisLah · Malaysian invoicing', page_icon='🌿', layout='wide', initial_sidebar_state='expanded')
init_db()
apply_theme()
PAGES = ['Dashboard', 'Invoices', 'New invoice', 'Documents', 'LHDN guide', 'Settings']
ICONS = ['⌂', '▤', '＋', '▧', '✓', '⚙']
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'


def go(page: str, **kwargs):
    st.session_state.page = page
    for key, value in kwargs.items():
        st.session_state[key] = value
    st.rerun()


def hero(kicker: str, title: str, description: str):
    st.markdown(f'''<div class="hero"><div class="hero-label">{escape(kicker)}</div>
    <div class="hero-title">{escape(title)}</div><div class="hero-p">{escape(description)}</div></div>''', unsafe_allow_html=True)


def section(title: str):
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)


def stat(icon: str, label: str, value: str, foot: str = ''):
    st.markdown(f'''<div class="stat-card"><div class="stat-icon">{escape(icon)}</div>
        <p class="stat-label">{escape(label)}</p><p class="stat-number">{escape(value)}</p>
        <p class="stat-foot">{escape(foot)}</p></div>''', unsafe_allow_html=True)


def quick(icon: str, heading: str, sub: str):
    st.markdown(f'''<div class="quick-card"><div class="quick-head">{escape(icon)}</div>
    <div class="quick-name">{escape(heading)}</div><div class="quick-sub">{escape(sub)}</div></div>''', unsafe_allow_html=True)


def rows_to_frame(invoices: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        'Invoice #': inv['invoice_number'], 'Client': inv['client_name'],
        'Issued': inv['issue_date'], 'Due': inv['due_date'],
        'Amount': fmt(inv['total_amount'], inv['currency']),
        'Payment': effective_status(inv).capitalize(),
        'LHDN': 'Not submitted',
    } for inv in invoices])


def sidebar():
    with st.sidebar:
        st.markdown('<div class="brand">🌿 Invois<span class="brand-dot">Lah</span></div>', unsafe_allow_html=True)
        st.caption('YOUR BUSINESS, BEAUTIFULLY ORGANIZED')
        st.markdown('')
        for icon, page in zip(ICONS, PAGES):
            if st.button(f'{icon}   {page}', key=f'nav_{page}', use_container_width=True,
                         type='primary' if st.session_state.page == page else 'secondary'):
                go(page)
        st.divider()
        st.caption('LOCAL PROTOTYPE  ·  NOT CONNECTED TO LHDN')
        st.caption('Records stay on this machine. Use a secured server and user authentication before a public launch.')


def dashboard():
    hero('GOOD TO HAVE YOU HERE', 'Your business, in full bloom.',
         'Create professional invoices, stay on top of payments, and keep your documents in one calm place.')
    invoices = list_invoices()
    paid = [x for x in invoices if effective_status(x) == 'paid']
    def to_myr(inv):
        return money(inv['total_amount']) * Decimal(str(inv.get('exchange_rate') or '1'))
    revenue = sum((to_myr(x) for x in paid), Decimal('0'))
    pending = sum(effective_status(x) == 'pending' for x in invoices)
    overdue = sum(effective_status(x) == 'overdue' for x in invoices)
    cols = st.columns(4, gap='small')
    vals = [('▤','Total invoices',str(len(invoices)),'All local records'),
            ('↗','Paid revenue',fmt(revenue),'MYR-equivalent · entered FX'),
            ('◷','Awaiting payment',str(pending),'Not yet overdue'),
            ('!','Overdue invoices',str(overdue),'Follow up with clients')]
    for col, args in zip(cols, vals):
        with col:
            stat(*args)
    section('Quick actions')
    a,b,c = st.columns(3, gap='medium')
    with a:
        quick('✍', 'Create an invoice', 'Draft, price and send a professional invoice.')
        if st.button('Create new  →', use_container_width=True, type='primary', key='dash_create'):
            go('New invoice', edit_id=None)
    with b:
        quick('📷', 'Capture a document', 'Upload a receipt or take a photo on your device.')
        if st.button('Open document inbox  →', use_container_width=True, key='dash_docs'):
            go('Documents')
    with c:
        quick('✓', 'Check e-Invoice readiness', 'Review local data completeness and LHDN guidance.')
        if st.button('View LHDN guide  →', use_container_width=True, key='dash_guide'):
            go('LHDN guide')
    section('Recent invoices')
    if invoices:
        st.dataframe(rows_to_frame(invoices[:6]), hide_index=True, use_container_width=True)
        if st.button('View all invoices  →', key='dash_all'):
            go('Invoices')
    else:
        st.info('No invoices yet. Create your first invoice to see real totals and activity here — no sample figures.')
    st.markdown('''<div class="note"><b>Good to know:</b> A saved invoice is a local business record, not a validated
    e-Invoice. Official LHDN acceptance requires MyInvois submission and validation.</div>''', unsafe_allow_html=True)


def item_editor_frame(items):
    if items:
        return pd.DataFrame([{
            'Description': i['description'], 'Classification': i.get('classification_code') or '022',
            'Qty': float(i['quantity']), 'Unit price': float(i['unit_price']),
            'Tax type': i.get('tax_type') or '06', 'Tax rate %': float(i['tax_rate']),
        } for i in items])
    return pd.DataFrame([{
        'Description': '', 'Classification': '022', 'Qty': 1.0, 'Unit price': 0.0,
        'Tax type': '06', 'Tax rate %': 0.0,
    }])


def invoice_editor(existing_id: str | None = None):
    existing = get_invoice(existing_id) if existing_id else None
    if existing_id and not existing:
        st.error('Invoice not found.'); return
    old, old_items = existing if existing else ({}, [])
    heading = 'Edit invoice' if existing else 'Create a new invoice'
    hero('INVOICE STUDIO', heading,
         'Build your invoice in one place. Drafts may omit official taxpayer details; issuing a local invoice checks key taxpayer fields.')
    st.caption('Invoice PDFs are local copies. No invoice here is sent to LHDN or given a validation QR.')
    profile = get_profile()
    with st.form(f'invoice_form_{existing_id or "new"}', clear_on_submit=False):
        st.subheader('01  Invoice information')
        x1,x2,x3 = st.columns([1.4,1,1])
        with x1:
            invoice_number = st.text_input('Invoice number *', value=old.get('invoice_number') or suggest_invoice_number(), max_chars=50)
        with x2:
            issue_date = st.date_input('Issue date *', value=date.fromisoformat(old['issue_date']) if old else date.today())
        with x3:
            due_date = st.date_input('Due date *', value=date.fromisoformat(old['due_date']) if old else date.today() + timedelta(days=14))
        c1,c2 = st.columns([1,1])
        with c1:
            currency = st.selectbox('Currency', CURRENCIES, index=CURRENCIES.index(old.get('currency') or 'MYR'))
        with c2:
            rate = st.number_input('Exchange rate → MYR', min_value=0.0, value=float(old.get('exchange_rate') or 1), step=0.01,
                                   help='How many MYR equal one unit of selected currency. Required for non-MYR invoices.')
        st.divider()
        st.subheader('02  Bill to')
        client_name = st.text_input('Buyer / client name *', value=old.get('client_name',''))
        p1,p2,p3 = st.columns([1.1, .7, 1.1])
        with p1: client_tin = st.text_input('Buyer TIN', value=old.get('client_tin',''))
        with p2:
            id_type_value = old.get('client_id_type') or 'BRN'
            client_id_type = st.selectbox('ID type', ID_TYPES, index=ID_TYPES.index(id_type_value) if id_type_value in ID_TYPES else 0)
        with p3: client_id_number = st.text_input('ID / registration no.', value=old.get('client_id_number',''))
        u,v = st.columns(2)
        with u: client_email = st.text_input('Email (optional)', value=old.get('client_email',''))
        with v: client_phone = st.text_input('Phone', value=old.get('client_phone',''))
        client_address = st.text_input('Address line', value=old.get('client_address',''))
        a,b,c,d = st.columns([1.2,.8,.8,.7])
        with a: client_city = st.text_input('City', value=old.get('client_city',''))
        with b: client_postcode = st.text_input('Postcode', value=old.get('client_postcode',''))
        with c: client_state = st.text_input('State code', value=old.get('client_state_code',''), help='Use the official MyInvois state code list.')
        with d: client_country = st.text_input('Country', value=old.get('client_country_code') or 'MYS', max_chars=3)
        st.divider()
        st.subheader('03  Products & services')
        st.caption('Add/remove rows. Classification example: 022 = Others. Verify official codes and tax treatment before any submission.')
        df = st.data_editor(item_editor_frame(old_items), key=f'items_{existing_id or "new"}', num_rows='dynamic',
            hide_index=True, use_container_width=True,
            column_config={
                'Description': st.column_config.TextColumn('Description', required=True, width='large'),
                'Classification': st.column_config.TextColumn('LHDN class', help='Three-digit code; 022 = Others'),
                'Qty': st.column_config.NumberColumn('Qty', min_value=0.01, step=1.0),
                'Unit price': st.column_config.NumberColumn('Unit price', min_value=0.0, step=1.0, format='%.2f'),
                'Tax type': st.column_config.SelectboxColumn('Tax type', options=list(TAX_TYPES), required=True),
                'Tax rate %': st.column_config.NumberColumn('Tax %', min_value=0.0, max_value=100.0, step=1.0),
            })
        st.caption('Tax types: ' + ' · '.join(f'{k} {v}' for k,v in TAX_TYPES.items()))
        st.divider()
        st.subheader('04  Adjustments & notes')
        t1,t2 = st.columns(2)
        with t1:
            discount_percent = st.number_input('Discount (%)', min_value=0.0, max_value=100.0, step=1.0, value=float(old.get('discount_percent') or 0))
        with t2:
            shipping_fee = st.number_input('Additional charges', min_value=0.0, step=1.0, value=float(old.get('shipping_fee') or 0),
                help='Tax is not automatically applied to extra charges. Review treatment before formal submission.')
        notes = st.text_area('Payment details / notes', value=old.get('notes',''), height=90)
        st.caption('Taxes are calculated per line on the amount after the invoice discount. No fixed 6% or 8% rate is assumed.')
        left,right = st.columns(2)
        with left: draft = st.form_submit_button('Save as draft', use_container_width=True)
        with right: issue = st.form_submit_button('Issue local invoice', type='primary', use_container_width=True)
    if draft or issue:
        raw = df.to_dict('records')
        items = []
        for r in raw:
            # Empty add-row placeholders should not block saving another valid row.
            if not str(r.get('Description') or '').strip() and not (r.get('Unit price') or 0):
                continue
            items.append({
                'description': str(r.get('Description') or '').strip(),
                'classification_code': str(r.get('Classification') or '').strip(),
                'quantity': r.get('Qty') or 0, 'unit_price': r.get('Unit price') or 0,
                'tax_type': str(r.get('Tax type') or '06'), 'tax_rate': r.get('Tax rate %') or 0,
            })
        inv = {
            'invoice_number': invoice_number.strip(), 'client_name': client_name.strip(),
            'client_tin': client_tin.strip(), 'client_id_type': client_id_type,
            'client_id_number': client_id_number.strip(), 'client_email': client_email.strip(),
            'client_phone': client_phone.strip(), 'client_address': client_address.strip(),
            'client_city': client_city.strip(), 'client_postcode': client_postcode.strip(),
            'client_state_code': client_state.strip(), 'client_country_code': client_country.strip(),
            'issue_date': issue_date.isoformat(), 'due_date': due_date.isoformat(),
            'currency': currency, 'exchange_rate': str(rate),
            'discount_percent': str(discount_percent), 'shipping_fee': str(shipping_fee),
            'payment_status': ('pending' if issue else 'draft'), 'notes': notes,
        }
        errors, warnings = validate_invoice(inv, items, profile, for_issue=issue)
        try:
            if not errors:
                amounts = totals(items, discount_percent, shipping_fee)
                inv.update({k:v for k,v in [
                    ('subtotal',str(amounts['subtotal'])),('discount_amount',str(amounts['discount'])),
                    ('tax_amount',str(amounts['tax'])),('total_amount',str(amounts['total']))]})
                discount_rate = Decimal(str(discount_percent))
                for i in items:
                    price = money(i['unit_price'])
                    qty = Decimal(str(i['quantity']))
                    gross = (price*qty).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                    disc = (gross*discount_rate/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                    i['amount'] = str(gross)
                    i['tax_amount'] = str(((gross-disc)*Decimal(str(i['tax_rate']))/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
                saved_id = save_invoice(inv, items, existing_id)
                st.success(f"{'Local invoice issued' if issue else 'Draft saved'} · {invoice_number} · {fmt(amounts['total'], currency)}")
                for warning in warnings:
                    st.caption('⚠ ' + warning)
                if st.button('Go to invoice details  →', key='edit_done'):
                    go('Invoices', focus_id=saved_id, edit_id=None)
        except (ValueError, sqlite3.IntegrityError) as exc:
            errors.append('Cannot save invoice: ' + ('Invoice number already exists.' if isinstance(exc, sqlite3.IntegrityError) else str(exc)))
        for error in errors:
            st.error(error)
    section('Attach supporting documents')
    st.caption('To associate a receipt, save the invoice first, then open Documents and choose the invoice. Camera and upload are side by side there.')
    if existing_id:
        if st.button('📷  Upload or capture a receipt  →', key='to_docs_from_editor'):
            go('Documents', target_invoice=existing_id)


def invoices_page():
    hero('YOUR INVOICE LIBRARY', 'Everything in its place.', 'Search, edit, duplicate and download your invoices. Payment tracking is separate from LHDN validation.')
    data = list_invoices()
    t1,t2 = st.columns([2,1])
    with t1: term = st.text_input('Search client or invoice number', placeholder='e.g. INV-202611-0001')
    with t2: filter_status = st.selectbox('Payment status', ['All','Draft','Pending','Paid','Overdue','Cancelled'])
    filtered = [i for i in data if (term.lower() in (i['invoice_number'] + ' ' + i['client_name']).lower())
                and (filter_status=='All' or effective_status(i)==filter_status.lower())]
    if not data:
        st.info('Your invoice library is empty. Start by creating a draft.')
        if st.button('New invoice  →', type='primary', key='invoices_empty'):
            go('New invoice',edit_id=None)
        return
    st.dataframe(rows_to_frame(filtered), hide_index=True, use_container_width=True)
    sio=StringIO()
    w=csv.writer(sio); w.writerow(['invoice_number','client_name','issue_date','due_date','currency','total_amount','payment_status','lhdn_status'])
    for i in filtered:
        w.writerow([i[k] for k in ['invoice_number','client_name','issue_date','due_date','currency','total_amount','payment_status','lhdn_status']])
    st.download_button('↓ Export filtered CSV', sio.getvalue().encode('utf-8-sig'), 'invoislah-invoices.csv', 'text/csv')
    if not filtered:
        st.warning('No invoices match those filters.')
        return
    ids = [inv['id'] for inv in filtered]
    initial = ids.index(st.session_state.focus_id) if st.session_state.get('focus_id') in ids else 0
    chosen = st.selectbox('Open an invoice', ids, index=initial,
                          format_func=lambda x: next((f"{z['invoice_number']}  •  {z['client_name']}" for z in filtered if z['id']==x), x))
    result = get_invoice(chosen)
    if not result: return
    inv, items = result
    st.subheader(inv['invoice_number'])
    s1,s2,s3 = st.columns(3)
    s1.metric('Total', fmt(inv['total_amount'],inv['currency']))
    s2.metric('Payment', effective_status(inv).title())
    s3.metric('LHDN', 'Not submitted')
    st.caption(f"Buyer: {inv['client_name']}  ·  Issue: {inv['issue_date']}  ·  Due: {inv['due_date']}")
    st.dataframe(pd.DataFrame([{'Description':x['description'],'Class':x['classification_code'],
             'Qty':x['quantity'],'Price':fmt(x['unit_price'],inv['currency']),
             'Tax code':x['tax_type'],'Tax %':x['tax_rate']} for x in items]), hide_index=True, use_container_width=True)
    a,b,c=st.columns(3)
    with a:
        if st.button('✎  Edit', use_container_width=True, key='detail_edit'):
            go('New invoice', edit_id=chosen)
    with b:
        if st.button('⧉  Duplicate draft', use_container_width=True, key='duplicate'):
            clone={k:inv[k] for k in inv if k not in ('id','created_at','updated_at','lhdn_status')}
            clone['invoice_number']=suggest_invoice_number()
            clone['payment_status']='draft'
            new_id=save_invoice(clone, items)
            st.success('Created a new editable draft copy.')
            go('New invoice', edit_id=new_id)
    with c:
        st.download_button('↓  Download invoice PDF', invoice_pdf(inv,items,get_profile(), get_business_logo()),
                           file_name=inv['invoice_number']+'.pdf',mime='application/pdf',use_container_width=True)
    st.markdown('**Update payment status (local tracking only)**')
    val=inv['payment_status'] if inv['payment_status'] in ('draft','pending','paid','cancelled') else 'pending'
    choice=st.selectbox('New payment status', ['draft','pending','paid','cancelled'],
                        index=['draft','pending','paid','cancelled'].index(val))
    if st.button('Save payment status', key='save_status'):
        set_status(chosen,choice)
        st.success('Payment status updated; LHDN status unchanged.')
        st.rerun()
    with st.expander('Delete local invoice'):
        st.warning('This deletes a local record only. It does not cancel an invoice with LHDN.')
        if st.checkbox('I understand the local invoice will be deleted.', key='delete_confirm'):
            if st.button('Delete invoice permanently', key='delete_invoice'):
                delete_invoice(chosen)
                st.session_state.focus_id=None
                st.rerun()


def documents_page():
    hero('RECEIPT & DOCUMENT INBOX', 'Snap it. Save it. Find it.',
         'Upload an image or PDF, or take a picture directly with your phone or laptop camera.')
    st.markdown('<div class="eyebrow">ADD DOCUMENT</div>', unsafe_allow_html=True)
    left,right=st.columns(2, gap='medium')
    with left:
        st.markdown('**▤  Upload file**')
        uploaded=st.file_uploader('Choose JPEG, PNG or PDF',type=['jpg','jpeg','png','pdf'], key='doc_upload')
    with right:
        st.markdown('**📷  Take photo**')
        captured=st.camera_input('Open your camera and capture', key='doc_camera')
    invoices=list_invoices()
    options=['Unassigned']+[f"{x['invoice_number']} · {x['client_name']}" for x in invoices]
    ids=[None]+[x['id'] for x in invoices]
    target=st.session_state.get('target_invoice')
    idx=ids.index(target) if target in ids else 0
    selection=st.selectbox('Attach to invoice (optional)', options, index=idx, key='doc_attach')
    invoice_id=ids[options.index(selection)]
    if uploaded and captured:
        st.warning('Both sources are selected. Save one at a time by clearing the other source.')
    elif uploaded or captured:
        source='camera' if captured else 'upload'
        file=captured or uploaded
        if file.type.startswith('image/'):
            st.image(file, caption='Document preview', width=340)
        else:
            st.caption(f'PDF selected: {file.name}')
        if st.button('Save document', type='primary', key='save_document'):
            try:
                name=file.name if source=='upload' else f'camera-{datetime.now():%Y%m%d-%H%M%S}.jpg'
                save_attachment(name,file.getvalue(),file.type,source,invoice_id)
                st.success('Document saved to the local document inbox.')
                st.session_state.target_invoice=None
            except ValueError as exc:
                st.error(str(exc))
    else:
        st.caption('Camera access requires permission and generally works on localhost or HTTPS. Uploaded files are checked for supported file signatures and limited to 10 MB.')
    section('Saved documents')
    saved=list_attachments()
    if not saved:
        st.info('Nothing saved yet. Upload your first document or take a photo.')
        return
    invoice_lookup={i['id']: i['invoice_number'] for i in invoices}
    for attachment in saved:
        with st.expander(f"{'📷' if attachment['source']=='camera' else '▤'}  {attachment['original_name']}  ·  {attachment['created_at']}"):
            st.caption('Linked invoice: ' + invoice_lookup.get(attachment['invoice_id'],'Unassigned'))
            try:
                content=attachment_bytes(attachment)
            except OSError:
                st.error('Document file is missing on disk.'); continue
            if attachment['mime_type'].startswith('image/'):
                st.image(content,width=350)
            st.download_button('↓  Download',content,file_name=attachment['original_name'],
                               mime=attachment['mime_type'],key=f"dl_{attachment['id']}")
            if st.button('Delete stored document',key=f"del_doc_{attachment['id']}"):
                delete_attachment(attachment['id']); st.rerun()
    st.markdown('<div class="note">A receipt image is supporting evidence, not an issued or validated e-Invoice. OCR is not enabled; always verify extracted or entered amounts manually.</div>', unsafe_allow_html=True)


def guide_page():
    hero('LHDN KNOWLEDGE HUB', 'Stay prepared, stay accurate.',
         'Practical checkpoints informed by official HASiL guidance as available on 16 November 2026.')
    st.warning('InvoisLah is a local invoicing prototype, not a MyInvois intermediary or official submission tool.')
    st.subheader('Current implementation timeline')
    st.table(pd.DataFrame([
        ('More than RM100 million','1 August 2024'),
        ('More than RM25m, up to RM100m','1 January 2025'),
        ('More than RM5m, up to RM25m','1 July 2025'),
        ('Up to RM5m (subject to exemption rules)','1 January 2026'),
    ],columns=['Annual turnover / revenue','Scheduled date']))
    st.info('HASiL’s 30 August 2026 update states that taxpayers with annual turnover/revenue **below RM3 million** are exempt from implementation, subject to the detailed MSME eligibility rules and exceptions. Do not rely on the old RM150,000 freelancer threshold.')
    st.markdown('**Official guides:** [LHDN timeline](https://www.hasil.gov.my/en/e-invois/pelaksanaan-e-invois-di-malaysia/garis-masa-pelaksanaan-e-invois/) · [Guideline v4.8 and Specific Guideline v4.9](https://www.hasil.gov.my/en/e-invois/rujukan-pelaksanaan-e-invois/garis-panduan/) · [MSME FAQs](https://www.hasil.gov.my/wp-content/uploads/lhdnm-e-invoice-general-faqs.pdf)')
    section('Readiness checklist')
    checks=[
        ('Supplier identity','Business name, TIN, identity type/number, MSIC, activity, location, phone'),
        ('Buyer identity','Name, TIN, ID type and number, address, phone and other required details'),
        ('Invoice content','Unique document number, issue date/time, currency and FX where applicable'),
        ('Each line item','Product/service description, classification code, quantity, unit price and tax type'),
        ('Tax treatment','Choose correct tax type/rate per supply; exemptions need supporting treatment'),
        ('Official validation','Create the UBL document, authenticate, digitally sign as required, submit and obtain valid status'),
    ]
    for h,detail in checks:
        st.checkbox(h + ' — ' + detail, key=f'guide_{h}')
    st.caption('Checklist is educational and not a certification or live LHDN validation.')
    section('Important distinctions')
    st.markdown('''- **Draft / pending / paid** indicate **local payment tracking**, not LHDN submission status.
- **Not Submitted** is shown on all app-created documents. Never generate a fake MyInvois UUID or official validation QR.
- LHDN accepts structured **UBL 2.1 XML/JSON**, with core, tax, currency, code and other validations. A PDF alone is insufficient.
- The MyInvois SDK provides **tax codes 01–06 and E**. **Not Applicable (06)** is not a generic zero-rated tax, and **E** requires appropriate exemption treatment.
- A validated e-Invoice normally has a **72-hour cancellation/rejection window**; after that, corrections generally use the appropriate credit, debit or refund document. This app does not implement official cancellations.''')
    st.markdown('**SDK references:** [Tax types](https://sdk.myinvois.hasil.gov.my/codes/tax-types/) · [Classification codes](https://sdk.myinvois.hasil.gov.my/codes/classification-codes/) · [Document validation](https://sdk.myinvois.hasil.gov.my/document-validation-rules/) · [Cancellation workflow](https://sdk.myinvois.hasil.gov.my/einvoicingapi/03-cancel-document/)')
    section('What is still required before production integration?')
    st.markdown('''A secure user login and business-specific data separation; official code tables and field validators; full UBL 2.1 serialization; MyInvois OAuth/API credentials, digital signatures, submission/polling/validation and rejection handling; evidence retention and audit logs; security review; and professional SST/tax advice where applicable.''')


def settings_page():
    hero('BUSINESS PROFILE', 'A few details go a long way.', 'Use one verified supplier profile across all newly created local invoices.')
    old=get_profile()
    with st.form('profile_form'):
        st.subheader('Company / freelancer details')
        name=st.text_input('Supplier business name *',value=old['name'])
        a,b=st.columns(2)
        with a: email=st.text_input('Business email',value=old['email'])
        with b: phone=st.text_input('Business phone *',value=old['phone'])
        st.subheader('Registration')
        a,b,c=st.columns(3)
        with a: tin=st.text_input('LHDN TIN *',value=old['tin'])
        with b:
            id_type=st.selectbox('Registration / ID type',ID_TYPES,
                index=ID_TYPES.index(old['id_type']) if old['id_type'] in ID_TYPES else 0)
        with c: id_number=st.text_input('ID / BRN number *',value=old['id_number'])
        a,b=st.columns([.7,1.3])
        with a: msic=st.text_input('MSIC code *',value=old['msic'])
        with b: activity=st.text_input('Business activity description *',value=old['activity'])
        sst=st.text_input('SST registration number (if applicable)',value=old['sst_number'])
        st.subheader('Business address')
        address=st.text_input('Address line *',value=old['address'])
        a,b,c,d=st.columns([1.2,.8,.7,.7])
        with a: city=st.text_input('City *',value=old['city'])
        with b: postcode=st.text_input('Postcode *',value=old['postcode'])
        with c: state_code=st.text_input('State code *',value=old['state_code'])
        with d: country_code=st.text_input('Country',value=old['country_code'],max_chars=3)
        saved=st.form_submit_button('Save business profile',type='primary')
    if saved:
        data=locals()
        save_profile({k:data[k] for k in ['name','email','phone','tin','id_type','id_number','msic','activity','sst','address','city','postcode','state_code','country_code'] if k!='sst'}|{'sst_number':sst})
        st.success('Business profile saved locally.')
    section('Business logo · Upload or take a photo')
    st.caption('Optional branding for your local invoice PDF. A photo option appears beside upload.')
    lcol,rcol=st.columns(2)
    with lcol:
        logo_upload=st.file_uploader('Upload logo (JPG or PNG)',type=['jpg','jpeg','png'],key='logo_upload')
    with rcol:
        logo_camera=st.camera_input('Take a logo photo',key='logo_camera')
    old_logo=get_business_logo()
    if old_logo:
        st.image(old_logo,caption='Current business logo',width=130)
    if logo_upload and logo_camera:
        st.warning('Choose only one logo source at a time.')
    elif logo_upload or logo_camera:
        img=logo_camera or logo_upload
        st.image(img,caption='Preview logo',width=150)
        if st.button('Save business logo',key='save_logo'):
            try:
                save_business_logo(img.getvalue())
                st.success('Business logo saved and available on invoice PDFs.')
            except ValueError as exc:
                st.error(str(exc))
    st.markdown('''<div class="note"><b>Privacy:</b> This project uses local SQLite storage without sign-in. Do not host it publicly with real taxpayer IDs or receipts until authentication, backups, encryption, and access controls are implemented.</div>''', unsafe_allow_html=True)


sidebar()
page=st.session_state.page
if page=='Dashboard': dashboard()
elif page=='Invoices': invoices_page()
elif page=='New invoice': invoice_editor(st.session_state.get('edit_id'))
elif page=='Documents': documents_page()
elif page=='LHDN guide': guide_page()
elif page=='Settings': settings_page()
