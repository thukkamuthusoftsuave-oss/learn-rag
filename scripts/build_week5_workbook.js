/* Builds the editable Week 5 workbook without external dependencies. */
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const out = path.resolve(__dirname, '..', 'docs', 'week5-manual-review.xlsx');

const questions = [
  ['CORE-01', 'NA', 'What is the carry-over cap for a probationary employee in NA?', 'Answer from addendum_NA.txt, HR-207 Section 4.2'],
  ['CORE-02', 'EMEA', 'What is the carry-over cap for a regular employee with 1 year of service in EMEA?', 'Answer from addendum_EMEA.txt, Section 4.2'],
  ['CORE-03', 'APAC', 'What is the carry-over cap for a senior employee in APAC?', 'Answer from addendum_APAC.txt, Section 4.2'],
  ['CORE-04', 'LATAM', 'When does the HR-207 policy become effective in LATAM?', 'Answer from header of addendum_LATAM.txt'],
  ['CORE-05', 'US', 'What defines continuous service in US for the carry-over policy?', 'Answer from addendum_US.txt, Section 4.1'],
  ['CORE-06', 'UK', 'Who is eligible for the sabbatical in UK?', 'Answer from addendum_UK.txt, Section 4.3'],
  ['CORE-07', 'US', 'What is the max carry-over for a senior with > 2 years of service in US?', 'Answer from addendum_US.txt, Section 4.2'],
  ['CORE-08', 'NA', 'Does a regular employee in NA get 15 days carry-over cap?', 'Answer is no; check addendum_NA.txt, Section 4.2'],
  ['OOC-01', 'none', 'What is the maternity leave policy in EMEA?', 'Correct refusal; outside the corpus'],
  ['OOC-02', 'none', 'Who is eligible for sabbatical in LATAM?', 'Correct refusal; LATAM has no sabbatical clause'],
  ['OOC-03', 'none', 'What is the reimbursement limit for home office equipment?', 'Correct refusal; different policy family'],
  ['OOC-04', 'US', 'What is selfcare?', 'Correct refusal; not covered by the corpus'],
  ['EDGE-01', 'US', 'I am a part-time employee (20 hours/week) in the US and I have worked here for 3 years. How many carry-over days do I get?', 'Answer is 0 days; check addendum_US.txt, Section 4.7'],
  ['EDGE-02', 'NA', 'What happens to my carry-over balance if I resign without notice in NA?', 'Answer from addendum_NA.txt, Section 4.5'],
  ['EDGE-03', 'NA', 'Can a contract worker claim carry-over in NA?', 'Answer from addendum_NA.txt, Section 4.1'],
  ['EDGE-04', 'UK', 'When do carried-over days expire in UK?', 'Answer from addendum_UK.txt, Section 4.4'],
  ['EDGE-05', 'APAC', 'How do I submit a carry-over request in APAC?', 'Answer from addendum_APAC.txt, Section 4.8'],
  ['EDGE-06', 'EMEA', 'What is Section 4.9 about in EMEA?', 'Answer from addendum_EMEA.txt, Section 4.9'],
  ['EDGE-07', 'EMEA', 'What is the sabbatical duration and eligibility in EMEA?', 'Both facts required; check addendum_EMEA.txt, Section 4.3'],
  ['EDGE-08', 'US', 'Can I borrow vacation days in advance in US, and what is the limit?', 'Answer from addendum_US.txt, Section 4.6'],
];

const reviewRows = questions.map(([id]) => [id, '', '', '', '', '', '']);
const taxonomyRows = Array.from({ length: 6 }, (_, i) => [i + 1, '', '', '', '', { formula: `D${i + 2}*E${i + 2}` }, '']);
const predictionRows = [
  ['Chosen problem', ''],
  ['Evidence', '__ / 20 traces; severity __ / 5; score __'],
  ['One change only', ''],
  ['Prediction', ''],
  ['What it will not fix', ''],
];

function esc(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function col(index) {
  let result = '';
  for (let n = index + 1; n; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + (n - 1) % 26) + result;
  return result;
}

function cell(reference, value, style = 0) {
  if (value && typeof value === 'object' && value.formula) return `<c r="${reference}" s="${style}"><f>${esc(value.formula)}</f><v></v></c>`;
  if (value === '') return `<c r="${reference}" s="${style}"/>`;
  return `<c r="${reference}" t="inlineStr" s="${style}"><is><t xml:space="preserve">${esc(value)}</t></is></c>`;
}

function worksheet(headers, rows, widths) {
  const all = [headers, ...rows];
  const lastCol = col(headers.length - 1);
  const rowXml = all.map((row, r) => {
    const style = r === 0 ? 1 : 0;
    return `<row r="${r + 1}">${row.map((value, c) => cell(`${col(c)}${r + 1}`, value, style)).join('')}</row>`;
  }).join('');
  const cols = widths.map((width, i) => `<col min="${i + 1}" max="${i + 1}" width="${width}" customWidth="1"/>`).join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:${lastCol}${all.length}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>${cols}</cols><sheetData>${rowXml}</sheetData><autoFilter ref="A1:${lastCol}${all.length}"/></worksheet>`;
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function zip(entries) {
  const parts = [], central = [];
  let offset = 0;
  for (const [name, contents] of entries) {
    const file = Buffer.from(contents, 'utf8');
    const compressed = zlib.deflateRawSync(file);
    const nameBuf = Buffer.from(name);
    const crc = crc32(file);
    const local = Buffer.alloc(30 + nameBuf.length);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0, 6); local.writeUInt16LE(8, 8);
    local.writeUInt32LE(crc, 14); local.writeUInt32LE(compressed.length, 18); local.writeUInt32LE(file.length, 22);
    local.writeUInt16LE(nameBuf.length, 26); local.writeUInt16LE(0, 28); nameBuf.copy(local, 30);
    parts.push(local, compressed);
    const dir = Buffer.alloc(46 + nameBuf.length);
    dir.writeUInt32LE(0x02014b50, 0); dir.writeUInt16LE(20, 4); dir.writeUInt16LE(20, 6); dir.writeUInt16LE(0, 8); dir.writeUInt16LE(8, 10);
    dir.writeUInt32LE(crc, 16); dir.writeUInt32LE(compressed.length, 20); dir.writeUInt32LE(file.length, 24);
    dir.writeUInt16LE(nameBuf.length, 28); dir.writeUInt16LE(0, 30); dir.writeUInt16LE(0, 32); dir.writeUInt16LE(0, 36); dir.writeUInt32LE(0, 38); dir.writeUInt32LE(offset, 42); nameBuf.copy(dir, 46);
    central.push(dir); offset += local.length + compressed.length;
  }
  const centralSize = central.reduce((sum, part) => sum + part.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10); end.writeUInt32LE(centralSize, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, ...central, end]);
}

const sheets = [
  ['Questions', worksheet(['ID', 'Region', 'Question', 'Expected behaviour / policy to check'], questions, [14, 12, 76, 64])],
  ['Trace Review', worksheet(['ID', 'Trace ID / saved output', 'Retrieved sources correct?', 'Answer correct and complete?', 'Open-coding observation (write this first)', 'Proposed group', 'Severity 1-5'], reviewRows, [14, 24, 28, 31, 65, 32, 14])],
  ['Taxonomy', worksheet(['Priority', 'Problem group', 'Trace IDs', 'Count', 'Severity', 'Score (count x severity)', 'Why it happens / evidence'], taxonomyRows, [12, 35, 28, 12, 14, 27, 60])],
  ['Prediction', worksheet(['Field', 'Your answer'], predictionRows, [28, 95])],
];

const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`;
const workbook = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map(([name], i) => `<sheet name="${name}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets></workbook>`;
const workbookRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`;
const styles = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs></styleSheet>`;
const rootRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`;

const entries = [
  ['[Content_Types].xml', contentTypes],
  ['_rels/.rels', rootRels],
  ['xl/workbook.xml', workbook],
  ['xl/_rels/workbook.xml.rels', workbookRels],
  ['xl/styles.xml', styles],
  ...sheets.map(([, xml], i) => [`xl/worksheets/sheet${i + 1}.xml`, xml]),
];
fs.writeFileSync(out, zip(entries));
console.log(`Wrote ${out}`);
