import sqlite3
from datetime import date, timedelta
from decimal import Decimal
import pytest

import data_store as store
from invoice_logic import totals, validate_invoice, money
from pdf_export import invoice_pdf


def sample_item(**extra):
    return {'description':'Consulting','classification_code':'022','quantity':2,
            'unit_price':'100.00','tax_type':'02','tax_rate':'8',**extra}


def sample_invoice(**extra):
    d={'invoice_number':'INV-TEST-001','client_name':'Sample Co','client_tin':'C1234567890',
       'client_id_type':'BRN','client_id_number':'202201012345','client_address':'1 Jalan Sample',
       'client_city':'Cyberjaya','client_postcode':'63000','client_state_code':'10',
       'client_phone':'0123456789','client_country_code':'MYS','issue_date':date.today().isoformat(),
       'due_date':(date.today()+timedelta(days=14)).isoformat(),
       'currency':'MYR','exchange_rate':'1','discount_percent':'10',
       'shipping_fee':'5','payment_status':'draft','notes':'Test'}
    d.update(extra)
    return d


def supplier():
    return {'name':'Example Freelancer','tin':'IG1234567890','id_type':'NRIC',
            'id_number':'900101012345','msic':'62010','activity':'Software service',
            'address':'123 Main St','city':'Cyberjaya','postcode':'63000',
            'state_code':'10','country_code':'MYS','phone':'0121234567'}


def test_money_rounding_and_tax_after_discount():
    result=totals([sample_item()],10,5)
    assert result['subtotal']==Decimal('200.00')
    assert result['discount']==Decimal('20.00')
    assert result['tax']==Decimal('14.40')
    assert result['total']==Decimal('199.40')
    assert money('1.005')==Decimal('1.01')


def test_tax_exempt_cannot_have_positive_rate():
    with pytest.raises(ValueError):
        totals([sample_item(tax_type='E',tax_rate=8)])
    assert totals([sample_item(tax_type='06',tax_rate=0)])['tax']==0


def test_local_field_validations():
    invoice=sample_invoice()
    errors,warnings=validate_invoice(invoice,[sample_item()],supplier(),for_issue=True)
    assert errors==[]
    assert any('not implemented' in w.lower() for w in warnings)
    errors,_=validate_invoice(sample_invoice(client_tin='',client_phone=''),[sample_item()],supplier(),for_issue=True)
    assert any('buyer' in err.lower() for err in errors)
    errors,_=validate_invoice(sample_invoice(currency='USD',exchange_rate=0),[sample_item()],supplier())
    assert any('exchange rate' in err.lower() for err in errors)


def test_atomic_storage_status_and_duplicate_number(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA_DIR',tmp_path)
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'test.db')
    store.init_db()
    store.save_profile(supplier())
    assert store.get_profile()['name']=='Example Freelancer'
    inv=sample_invoice()
    inv.update({k:str(v) for k,v in totals([sample_item()],10,5).items() if k in ('subtotal','tax','total')})
    inv['tax_amount']='14.40';inv['total_amount']='199.40';inv['discount_amount']='20.00'
    item=sample_item(amount='200',tax_amount='14.40')
    first_id=store.save_invoice(inv,[item])
    assert store.get_invoice(first_id)[0]['lhdn_status']=='NOT_SUBMITTED'
    assert len(store.get_invoice(first_id)[1])==1
    with pytest.raises(sqlite3.IntegrityError):
        store.save_invoice(inv,[item])
    assert len(store.list_invoices())==1
    assert store.effective_status(store.get_invoice(first_id)[0],today='2030-01-01')=='draft'
    store.set_status(first_id,'pending')
    assert store.effective_status(store.get_invoice(first_id)[0],today='2030-01-01')=='overdue'
    store.set_status(first_id,'paid')
    assert store.effective_status(store.get_invoice(first_id)[0])=='paid'
    assert store.get_invoice(first_id)[0]['lhdn_status']=='NOT_SUBMITTED'
    assert store.suggest_invoice_number().startswith('INV-')
    assert invoice_pdf(store.get_invoice(first_id)[0],store.get_invoice(first_id)[1],supplier()).startswith(b'%PDF')
    store.delete_invoice(first_id)
    assert store.get_invoice(first_id) is None


def test_attachment_file_types_and_safety(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA_DIR',tmp_path)
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'attach.db')
    store.init_db()
    with pytest.raises(ValueError):
        store.save_attachment('bad.txt',b'script content','text/plain','upload')
    saved=store.save_attachment('../../name.png',b'\x89PNG\r\n\x1a\nhello','image/png','upload')
    x=store.list_attachments()[0]
    assert x['id']==saved
    assert x['stored_name'].endswith('.png')
    assert store.attachment_bytes(x).startswith(b'\x89PNG')
    store.delete_attachment(saved)
    assert not store.list_attachments()


def test_business_logo_upload(tmp_path, monkeypatch):
    from PIL import Image
    from io import BytesIO
    monkeypatch.setattr(store,'DATA_DIR',tmp_path)
    img=Image.new('RGB',(50,20),(173,212,126))
    data=BytesIO(); img.save(data,format='PNG')
    store.save_business_logo(data.getvalue())
    assert store.get_business_logo().startswith(b'\x89PNG')
    with pytest.raises(ValueError):
        store.save_business_logo(b'not-an-image')
