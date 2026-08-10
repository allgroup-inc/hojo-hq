const PptxGenJS = require('pptxgenjs');

const pres = new PptxGenJS();
pres.layout = 'LAYOUT_16x9';

// Color palette
const colors = {
  orange: 'FF6B35',
  navy: '003366',
  white: 'FFFFFF',
  lightGray: 'F5F5F5',
  mediumGray: 'E0E0E0',
  darkGray: '666666',
  textDark: '333333',
};

// Helper function for consistent title styling
function addTitle(slide, text, xPos = 0.5, yPos = 0.4) {
  slide.addText(text, {
    x: xPos, y: yPos, w: 9, h: 0.5,
    fontSize: 36, bold: true, color: colors.textDark, align: 'left', fontFace: 'Arial'
  });
}

// Helper function for section boxes
function addBoxSection(slide, x, y, w, h, bgColor, borderColor, borderWidth, content) {
  slide.addShape(pres.ShapeType.rect, {
    x: x, y: y, w: w, h: h,
    fill: { color: bgColor }, line: { color: borderColor, width: borderWidth }
  });

  if (content.title) {
    slide.addText(content.title, {
      x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.3,
      fontSize: content.titleSize || 16, bold: true, color: content.titleColor || colors.navy, fontFace: 'Arial'
    });
  }

  if (content.text) {
    slide.addText(content.text, {
      x: x + 0.2, y: y + (content.title ? 0.55 : 0.2), w: w - 0.4, h: h - (content.title ? 0.75 : 0.4),
      fontSize: content.textSize || 13, color: content.textColor || colors.textDark, fontFace: 'Arial'
    });
  }
}

// Slides will be added here
