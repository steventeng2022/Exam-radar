from io import BytesIO
from zipfile import ZipFile
import pytest
from crawler.parsers import parse_document,check_archive

def test_html_ignores_scripts_and_keeps_content():
    result=parse_document(b'<script>fake exam</script><main>real exam</main>','https://school.edu.tw/','text/html')
    assert result[0]['text']=='real exam'

def test_office_inflation_guard():
    blob=BytesIO()
    with ZipFile(blob,'w',compression=8) as archive:archive.writestr('huge.xml',b'x'*(65*1024*1024))
    with pytest.raises(ValueError,match='expanded'):check_archive(blob.getvalue())

def test_xlsx_sheet_provenance():
    from openpyxl import Workbook
    book=Workbook();book.active.title='高二';book.active.append(['數學A','1-1～2-2'])
    blob=BytesIO();book.save(blob)
    pages=parse_document(blob.getvalue(),'https://school.edu.tw/range.xlsx','application/octet-stream')
    assert pages[0]['sheet']=='高二' and '1-1～2-2' in pages[0]['text']
