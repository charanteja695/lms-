const path = require('path');
const fs = require('fs');

const playwrightPath = path.resolve(__dirname, '../ExamLMS_src/Lms_frontend_Gz/node_modules/playwright');
const { chromium } = require(playwrightPath);

(async () => {
  console.log("Launching Chromium for PDF rendering...");
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true
  });
  
  const page = await browser.newPage();
  const filePath = 'file:///' + path.resolve(__dirname, '../design_doc_source.html').replace(/\\/g, '/');
  console.log("Navigating to:", filePath);
  
  await page.goto(filePath, { waitUntil: 'load' });
  await page.waitForTimeout(2000);
  
  const outputPath = path.resolve(__dirname, '../ExamLMS_Complete_UI_Design.pdf');
  console.log("Printing to PDF:", outputPath);
  
  await page.pdf({
    path: outputPath,
    format: 'A4',
    printBackground: true,
    margin: {
      top: '12mm',
      bottom: '12mm',
      left: '10mm',
      right: '10mm'
    },
    displayHeaderFooter: true,
    headerTemplate: '<div style="font-size: 8px; font-family: Inter, sans-serif; color: #94A3B8; width: 100%; text-align: right; padding-right: 12mm;">ExamLMS UI/UX Design System Specification</div>',
    footerTemplate: '<div style="font-size: 8px; font-family: Inter, sans-serif; color: #94A3B8; width: 100%; display: flex; justify-content: space-between; padding: 0 12mm;"><span>Confidential & Proprietary • ExamLMS</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>'
  });
  
  await browser.close();
  const stats = fs.statSync(outputPath);
  console.log(`PDF successfully created: ${outputPath} (${stats.size.toLocaleString()} bytes)`);
})();
