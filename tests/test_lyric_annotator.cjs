/* Optional browser regression: NODE_PATH=<playwright node_modules> node tests/test_lyric_annotator.cjs */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
(async () => {
 const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:950},acceptDownloads:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const fixture={schema_version:1,note:'Synthetic test only',extra:{unchanged:[1,'two']},lines:[
   {id:'first',tokens:[['青い','あおい'],['空','そら']],anchor_start:1,anchor_end:3,keep:{locked:true}},
   {id:'second',text:'明るい朝',start:4,end:6,custom:'preserve'},
   {id:'third',text:'光の道',start:7,end:9},
   {id:'fourth',text:'<img src=x onerror="window.injected=true">',start:10,end:12}
  ]};
  await page.goto(pathToFileURL(path.resolve('tools/lyric-annotator.html')).href);
  await page.locator('#file').setInputFiles({name:'synthetic.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))});
  assert.equal(await page.locator('.lyric').count(),4);
  assert.equal(await page.locator('.words img').count(),0);
  await page.locator('.lyric[data-index="0"]').click();
  await page.locator('.brush[data-singer="hisayo"]').click();
  await page.locator('.lyric[data-index="1"]').click();
  await page.locator('.lyric[data-index="2"]').click({modifiers:['Shift']});
  await page.locator('#undo').click();
  assert.equal(await page.locator('.lyric[data-index="2"] .badge').textContent(),'未标注');
  await page.locator('#redo').click();
  assert.equal(await page.locator('.lyric[data-index="2"] .badge').textContent(),'阿部寿世');
  await page.locator('#add').click();await page.locator('#newName').fill('Guest Singer');
  await page.locator('#newColor').fill('#123456');await page.locator('#addForm button[type="submit"]').click();
  await page.locator('.lyric[data-index="3"]').click();
  const chorusColor=page.getByLabel('合唱颜色',{exact:true});await chorusColor.fill('#ff7700');await chorusColor.dispatchEvent('change');
  await page.locator('.brush[data-singer="duet"]').click();await page.locator('.lyric[data-index="2"]').click();
  const downloadWait=page.waitForEvent('download');await page.locator('#save').click();const download=await downloadWait;
  assert.equal(download.suggestedFilename(),'synthetic-annotated.json');
  const saved=JSON.parse(await fs.readFile(await download.path(),'utf8'));
  assert.deepEqual(saved.extra,fixture.extra);assert.deepEqual(saved.lines[0].tokens,fixture.lines[0].tokens);
  assert.deepEqual(saved.lines[0].keep,fixture.lines[0].keep);assert.equal(saved.lines[1].start,4);
  assert.equal(saved.lines[0].singer,'mao');assert.equal(saved.lines[1].singer,'hisayo');
  assert.equal(saved.lines[2].singer,'duet');assert.equal(saved.lines[3].singer,'singer_1');
  assert.equal(saved.singers.singer_1.color,'#123456');assert.equal(saved.singers.duet.color,'#ff7700');
  await page.locator('#file').setInputFiles({name:'roundtrip.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
  assert.equal(await page.locator('.lyric[data-index="3"] .badge').textContent(),'Guest Singer');
  assert.equal(await page.locator('#assigned').textContent(),'4');
  await page.locator('#file').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from('{bad')});
  assert.match(await page.locator('#status').textContent(),/载入失败/);
  assert.equal(await page.locator('.lyric').count(),4); // Invalid input preserves current work.
  await page.locator('#file').setInputFiles({name:'times.lrc',mimeType:'text/plain',buffer:Buffer.from('[00:01.50][00:04.00]青い空\n[00:08.20]光の道')});
  assert.equal(await page.locator('.lyric').count(),3);
  const lrc=await page.evaluate(()=>exportDoc());assert.deepEqual(lrc.lines.map(l=>l.start),[1.5,4,8.2]);
  const long={schema_version:1,lines:Array.from({length:60},(_,i)=>({id:`l-${i}`,text:`テスト ${i+1}`}))};
  await page.locator('#file').setInputFiles({name:'long.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(long))});
  const sidebarBefore=await page.locator('aside').boundingBox();
  await page.evaluate(()=>window.scrollTo(0,2200));await page.waitForTimeout(100);
  const sidebarAfter=await page.locator('aside').boundingBox();
  assert.ok(Math.abs(sidebarAfter.y-sidebarBefore.y)<2,'Singer sidebar must remain sticky while lyrics scroll');
  assert.ok(sidebarAfter.y+sidebarAfter.height<=952,'Sidebar fits the visible viewport');
  await page.locator('.brush[data-singer="hisayo"]').click();
  assert.equal(await page.locator('.brush[data-singer="hisayo"]').getAttribute('aria-pressed'),'true');
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.locator('#file').setInputFiles({name:'synthetic.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});
  await page.screenshot({path:'/tmp/auto-karaoke-annotator.png',fullPage:true});
  assert.deepEqual(errors,[]);
  await fs.writeFile('/tmp/auto-karaoke-annotated-test.json',JSON.stringify(saved,null,2));
  console.log('PASS: load, safe text, single/range marks, undo/redo, custom singer/color, chorus, save/reload, invalid file recovery, LRC.');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
