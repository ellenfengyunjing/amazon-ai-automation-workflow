// Optional visual QA for the generated local HTML; uses the project's existing
// playwright-core dependency and an explicitly selected browser executable.
const {chromium}=require('playwright-core');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const [executablePath,outDir,...files]=process.argv.slice(2);
 if(!executablePath||!outDir||!files.length)throw new Error('browser executable, output directory and HTML files required');
 fs.mkdirSync(outDir,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath});
 const rows=[];
 try{
  for(let i=0;i<files.length;i++){
   const page=await browser.newPage({viewport:{width:1280,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(pathToFileURL(path.resolve(files[i])).href);
   await page.locator('h1').waitFor();
   const heading=await page.locator('h1').innerText();
   const shot=path.join(outDir,`report-${i+1}.png`);
   if(fs.existsSync(shot))throw new Error('Refusing to overwrite screenshot');
   await page.screenshot({path:shot,fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   rows.push({file:path.resolve(files[i]),heading,errors,horizontal_overflow:overflow,screenshot:path.resolve(shot)});
   await page.close();
  }
 }finally{await browser.close();}
 const report=path.join(outDir,'browser-checks.json');
 fs.writeFileSync(report,JSON.stringify(rows,null,2),{flag:'wx'});
 process.stdout.write(JSON.stringify(rows)+'\n');
 if(rows.some(r=>r.errors.length||r.horizontal_overflow))process.exitCode=2;
})().catch(e=>{console.error(e);process.exitCode=1});
