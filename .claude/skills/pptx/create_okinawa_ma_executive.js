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

// Slide 1: Title
let slide = pres.addSlide();
slide.background = { color: colors.white };

slide.addText('沖縄県M&A市場', {
  x: 0.5, y: 1.8, w: 9, h: 0.8,
  fontSize: 54, bold: true, color: colors.textDark, align: 'center', fontFace: 'Arial'
});

slide.addText('× GLOW戦略', {
  x: 0.5, y: 2.8, w: 9, h: 0.8,
  fontSize: 54, bold: true, color: colors.orange, align: 'center', fontFace: 'Arial'
});

slide.addText('ギャップ市場の機会と実現戦略', {
  x: 0.5, y: 3.8, w: 9, h: 0.5,
  fontSize: 28, color: colors.navy, align: 'center', fontFace: 'Arial'
});

// Slide 2: Market Gap
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, '沖縄県M&A市場：ギャップ市場の定義');

// Left side: Problem
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 1.2, w: 4.3, h: 1.8,
  fill: { color: colors.lightGray }, line: { color: colors.orange, width: 3 }
});

slide.addText('市場の課題', {
  x: 0.7, y: 1.35, w: 4, h: 0.35,
  fontSize: 20, bold: true, color: colors.orange, fontFace: 'Arial'
});

slide.addText('後継者不安率\n65-70%\n（推定4,000-4,500社）', {
  x: 0.7, y: 1.85, w: 4, h: 1,
  fontSize: 24, bold: true, color: colors.textDark, fontFace: 'Arial'
});

// Arrow
slide.addShape(pres.ShapeType.line, {
  x: 4.9, y: 2.1, w: 0.8, h: 0,
  line: { color: colors.textDark, width: 3, endArrowType: 'triangle' }
});

// Right side: Opportunity
slide.addShape(pres.ShapeType.rect, {
  x: 5.2, y: 1.2, w: 4.3, h: 1.8,
  fill: { color: colors.lightGray }, line: { color: colors.navy, width: 3 }
});

slide.addText('市場の機会', {
  x: 5.4, y: 1.35, w: 4, h: 0.35,
  fontSize: 20, bold: true, color: colors.navy, fontFace: 'Arial'
});

slide.addText('年間成約\n120-150件\n（成約率2-3%）', {
  x: 5.4, y: 1.85, w: 4, h: 1,
  fontSize: 24, bold: true, color: colors.textDark, fontFace: 'Arial'
});

// Explanation box
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 3.2, w: 9, h: 2,
  fill: { color: colors.lightGray }, line: { color: colors.orange, width: 1 }
});

slide.addText('ギャップの実相', {
  x: 0.7, y: 3.35, w: 8.6, h: 0.3,
  fontSize: 16, bold: true, color: colors.orange, fontFace: 'Arial'
});

slide.addText('後継者不安企業4,000-4,500社に対して、実際のM&A成約は年間120-150件（成約率2-3%）。つまり、ほとんどのオーナーが成約に至っていない巨大なギャップ市場である。市場規模は推定¥300-500B、成長率は+50%/3年で拡大中。', {
  x: 0.7, y: 3.75, w: 8.6, h: 1.3,
  fontSize: 12, color: colors.textDark, fontFace: 'Arial'
});

// Slide 3: Why Gap Exists
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, 'なぜギャップが生まれるのか：3つの理由');

const reasons = [
  {
    num: '1',
    title: '既存M&A業者が小規模案件に対応しない',
    desc: 'ビジネスモデルの採算性の問題\n小規模案件は仲介手数料が固定費で賄えず、大型案件に特化する戦略'
  },
  {
    num: '2',
    title: '沖縄特有のリスク・文化的抵抗',
    desc: '親族承継志向が強く、M&Aリテラシーが低い\n経営者の「今は大丈夫」という現状維持バイアス'
  },
  {
    num: '3',
    title: '経営者心理の保守性',
    desc: 'トリガー発動までの準備段階で接触不足\n危機が現在化して初めて検討→時間がない'
  }
];

let yPos = 1.2;
reasons.forEach((item, idx) => {
  const borderColor = idx === 0 ? colors.orange : (idx === 1 ? colors.navy : colors.textDark);

  slide.addShape(pres.ShapeType.ellipse, {
    x: 0.5, y: yPos - 0.15, w: 0.5, h: 0.5,
    fill: { color: borderColor }, line: { color: borderColor, width: 0 }
  });

  slide.addText(item.num, {
    x: 0.5, y: yPos - 0.15, w: 0.5, h: 0.5,
    fontSize: 18, bold: true, color: colors.white, align: 'center', valign: 'middle', fontFace: 'Arial'
  });

  slide.addText(item.title, {
    x: 1.2, y: yPos - 0.1, w: 8.3, h: 0.35,
    fontSize: 16, bold: true, color: colors.textDark, fontFace: 'Arial'
  });

  slide.addText(item.desc, {
    x: 1.2, y: yPos + 0.3, w: 8.3, h: 0.6,
    fontSize: 12, color: colors.textDark, fontFace: 'Arial'
  });

  yPos += 1.15;
});

// Slide 4: Competitive Landscape
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, '沖縄のM&A業者ランドスケープ');

const tableData = [
  ['業者名', '対象案件規模', '報酬体系', '営業スタイル', '小規模対応'],
  ['大手仲介A', '5-50億円', '2-3%', '直接提案', '×（採算割れ）'],
  ['地域中堅B', '3-20億円', '3-4%', '紹介ベース', '△（限定的）'],
  ['金融系C', '2-10億円', '2.5-3.5%', '取引先営業', '△（融資対象のみ）'],
  ['地場小規模D', '1-5億円', '4-5%', '不定期', '○（実績薄）']
];

const headerBgColor = colors.navy;
const altRowBgColor = colors.lightGray;

let tableY = 1.3;
const cellHeight = 0.45;
const colWidths = [1.6, 1.8, 1.4, 1.8, 1.8];

tableData.forEach((row, rowIdx) => {
  let cellX = 0.5;

  row.forEach((cell, colIdx) => {
    const cellWidth = colWidths[colIdx];
    const bgColor = rowIdx === 0 ? headerBgColor : (rowIdx % 2 === 0 ? colors.white : altRowBgColor);
    const textColor = rowIdx === 0 ? colors.white : colors.textDark;
    const fontSize = rowIdx === 0 ? 11 : 9;
    const bold = rowIdx === 0;

    slide.addShape(pres.ShapeType.rect, {
      x: cellX, y: tableY, w: cellWidth, h: cellHeight,
      fill: { color: bgColor }, line: { color: colors.navy, width: 1 }
    });

    slide.addText(cell, {
      x: cellX + 0.05, y: tableY, w: cellWidth - 0.1, h: cellHeight,
      fontSize: fontSize, bold: bold, color: textColor, align: 'center', valign: 'middle', fontFace: 'Arial'
    });

    cellX += cellWidth;
  });

  tableY += cellHeight;
});

slide.addText('注：小規模対応 ○=対応可能／△=限定的／×=基本対応せず', {
  x: 0.5, y: 4.9, w: 9, h: 0.3,
  fontSize: 10, color: colors.textDark, fontFace: 'Arial', align: 'left'
});

// Slide 5: Why No Small Deal Support
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, 'なぜ既存業者は小規模案件に対応しないのか');

const reasons5 = [
  {
    title: '採算性の壁',
    content: '小規模案件（¥1-5B）の仲介手数料2-3% = ¥20-150M\n営業人件費（年¥8-12M）で利益なし→大型案件に特化',
    borderColor: colors.orange
  },
  {
    title: '営業効率の最適化',
    content: '既存ネットワーク（金融機関・上場企業）の紹介案件に特化\n新規開拓（小規模層）には営業コストがかかりすぎる',
    borderColor: colors.navy
  },
  {
    title: 'リスク回避',
    content: '小規模経営者は経営基盤が不安定→交渉が長引く\n既存業者は確実性の高い大型案件に集中',
    borderColor: colors.textDark
  }
];

let yPos5 = 1.3;
reasons5.forEach(item => {
  slide.addShape(pres.ShapeType.rect, {
    x: 0.5, y: yPos5, w: 9, h: 1,
    fill: { color: colors.lightGray }, line: { color: item.borderColor, width: 2 }
  });

  slide.addText(item.title, {
    x: 0.7, y: yPos5 + 0.08, w: 3, h: 0.25,
    fontSize: 14, bold: true, color: item.borderColor, fontFace: 'Arial'
  });

  slide.addText(item.content, {
    x: 4, y: yPos5 + 0.08, w: 5.3, h: 0.85,
    fontSize: 11, color: colors.textDark, fontFace: 'Arial'
  });

  yPos5 += 1.15;
});

slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 4.6, w: 9, h: 0.8,
  fill: { color: colors.lightGray }, line: { color: colors.navy, width: 1 }
});

slide.addText('→ GLOWの差別化：小規模案件専門 + 複数収益柱（M&A + 保険 + 経営相談）で採算化', {
  x: 0.7, y: 4.7, w: 8.6, h: 0.6,
  fontSize: 12, bold: true, color: colors.navy, fontFace: 'Arial'
});

// Slide 6: Risk Matrix
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, 'リスク要因分析：沖縄特有');

const riskData = [
  ['リスク', '説明', '影響度', '確度', '対策'],
  ['親族承継志向', 'オーナーの「事業は家族へ」という文化的信念が強い', '高', '高', 'シナリオ提示'],
  ['M&Aリテラシー不足', '経営者がM&A自体の仕組みを理解していない', '高', '高', '段階的教育'],
  ['観光経済依存', 'インバウンド減少時の景気変動リスク', '中', '中', 'シナリオプラン'],
  ['農業・建設高齢化', '経営者の急速な高齢化→廃業タイミングの予測難', '高', '高', '早期接触'],
];

let riskTableY = 1.3;
const riskCellHeight = 0.52;
const riskColWidths = [1.5, 3, 1.2, 1.2, 1.6];

riskData.forEach((row, rowIdx) => {
  let cellX = 0.5;

  row.forEach((cell, colIdx) => {
    const cellWidth = riskColWidths[colIdx];
    const bgColor = rowIdx === 0 ? colors.navy : (rowIdx % 2 === 0 ? colors.white : colors.lightGray);
    const textColor = rowIdx === 0 ? colors.white : colors.textDark;
    const fontSize = rowIdx === 0 ? 10 : 8.5;
    const bold = rowIdx === 0;

    slide.addShape(pres.ShapeType.rect, {
      x: cellX, y: riskTableY, w: cellWidth, h: riskCellHeight,
      fill: { color: bgColor }, line: { color: colors.navy, width: 1 }
    });

    slide.addText(cell, {
      x: cellX + 0.05, y: riskTableY + 0.02, w: cellWidth - 0.1, h: riskCellHeight - 0.04,
      fontSize: fontSize, bold: bold, color: textColor, align: 'center', valign: 'middle', fontFace: 'Arial'
    });

    cellX += cellWidth;
  });

  riskTableY += riskCellHeight;
});

// Slide 7: Mitigation Strategies
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, 'リスク対策：実装戦略');

const strategies = [
  {
    title: '親族承継志向への対抗戦略',
    points: [
      'アプローチ：「親族が引き継ぎたくない理由」のヒアリング',
      '施策：その課題を「外部統合」で解決する提案',
      'トリガー：患者獲得、スタッフ確保の困難を言語化'
    ]
  },
  {
    title: 'M&Aリテラシー向上',
    points: [
      '段階的フロー：補助金情報 → 経営相談 → M&A理解 → 提案',
      '沖縄での実例3-5件を紹介',
      '成功ストーリーで心理的抵抗を低減'
    ]
  },
  {
    title: '農業・建設の早期接触',
    points: [
      'タイムリミット：今後1-2年が最後の機会',
      '月間訪問：20-30社/月で市場開拓',
      '優先度：建設5,539社 + 農業推定3,000+社'
    ]
  }
];

let stratY = 1.3;
strategies.forEach(strat => {
  slide.addShape(pres.ShapeType.rect, {
    x: 0.5, y: stratY, w: 9, h: 1.2,
    fill: { color: colors.lightGray }, line: { color: colors.navy, width: 1 }
  });

  slide.addText(strat.title, {
    x: 0.7, y: stratY + 0.1, w: 8.6, h: 0.2,
    fontSize: 13, bold: true, color: colors.navy, fontFace: 'Arial'
  });

  slide.addText(strat.points.join('\n'), {
    x: 0.7, y: stratY + 0.35, w: 8.6, h: 0.75,
    fontSize: 10, color: colors.textDark, fontFace: 'Arial'
  });

  stratY += 1.35;
});

// Slide 8: Entrepreneur Psychology - Contradiction & Patterns
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, '経営者心理メカニズム：なぜ後継者不安なのに成約しないか');

// Three layers
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 1.3, w: 9, h: 0.9,
  fill: { color: colors.lightGray }, line: { color: colors.orange, width: 2 }
});

slide.addText('Layer 1: 矛盾の説明', {
  x: 0.7, y: 1.4, w: 2, h: 0.2,
  fontSize: 13, bold: true, color: colors.orange, fontFace: 'Arial'
});

slide.addText('後継者不安65-70% ←→ 成約率2-3%\n理由：「不安だが、今は大丈夫」という現状維持バイアス（心理学用語：喪失回避性、家族執着）', {
  x: 3, y: 1.4, w: 6.3, h: 0.7,
  fontSize: 11, color: colors.textDark, fontFace: 'Arial'
});

// Patterns
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 2.4, w: 9, h: 0.3,
  fill: { color: colors.navy }, line: { color: colors.navy, width: 0 }
});

slide.addText('Layer 2: 沖縄経営者に共通する3つのパターン', {
  x: 0.7, y: 2.45, w: 8.6, h: 0.2,
  fontSize: 13, bold: true, color: colors.white, fontFace: 'Arial'
});

const patterns = [
  {
    name: '親族重視型（40-50%）',
    desc: '「事業は子ども・親族へ」という信念が強い。親族に相談→反対される→立ち消え。'
  },
  {
    name: '保守型（30-40%）',
    desc: '変化回避、既存方法の継続を好む。「今までうまくいった」に依存。M&A検討も先延ばし。'
  },
  {
    name: '自己実現型（10-20%）',
    desc: '事業への執着が強く、人生＝経営者。引き継ぎ＝喪失感。「まだやれる」という過信。'
  }
];

let patY = 2.85;
patterns.forEach(pat => {
  slide.addText(pat.name, {
    x: 0.7, y: patY, w: 8.6, h: 0.2,
    fontSize: 11, bold: true, color: colors.textDark, fontFace: 'Arial'
  });

  slide.addText(pat.desc, {
    x: 0.7, y: patY + 0.25, w: 8.6, h: 0.45,
    fontSize: 10, color: colors.textDark, fontFace: 'Arial'
  });

  patY += 0.8;
});

// Slide 9: Decision Triggers
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, 'M&A決断のトリガー：業界別');

const triggers = [
  {
    industry: '医療・介護',
    trigger: 'トリガー：患者が減少 / 医師・看護師が逃げた / 負債が増えた',
    psychology: '心理：経営環境の急変 = 現状維持不可',
    timing: 'タイミング：危機が現在進行形→決断が早い'
  },
  {
    industry: '建設業',
    trigger: 'トリガー：大型工事が急減 / 下請けから外された / 若い職人が集まらない',
    psychology: '心理：事業基盤の揺らぎ→統合で大型案件対応',
    timing: 'タイミング：景気サイクルの悪化時期'
  },
  {
    industry: '農業・畜産',
    trigger: 'トリガー：体力の限界 / 跡継ぎが明確に拒否 / 借金が増えた',
    psychology: '心理：加齢とともに「続けられない」という現実認識',
    timing: 'タイミング：経営者が65歳を超えた時期'
  }
];

let trigY = 1.3;
triggers.forEach(trig => {
  slide.addShape(pres.ShapeType.roundRect, {
    x: 0.5, y: trigY, w: 9, h: 1.2,
    fill: { color: colors.lightGray }, line: { color: colors.navy, width: 1 }
  });

  slide.addText(trig.industry, {
    x: 0.7, y: trigY + 0.08, w: 8.6, h: 0.2,
    fontSize: 12, bold: true, color: colors.navy, fontFace: 'Arial'
  });

  slide.addText(`${trig.trigger}\n${trig.psychology}\n${trig.timing}`, {
    x: 0.7, y: trigY + 0.32, w: 8.6, h: 0.8,
    fontSize: 9.5, color: colors.textDark, fontFace: 'Arial'
  });

  trigY += 1.35;
});

// Implication
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 4.75, w: 9, h: 0.7,
  fill: { color: colors.lightGray }, line: { color: colors.navy, width: 1 }
});

slide.addText('→ GLOWの戦略：トリガー発動前の準備段階（信頼構築3-6ヶ月）で接触。トリガー発動時に即座に対応できる提案を用意', {
  x: 0.7, y: 4.85, w: 8.6, h: 0.5,
  fontSize: 11, bold: true, color: colors.navy, fontFace: 'Arial'
});

// Slide 10: GLOW Differentiation & Revenue Model
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, 'GLOW戦略的ポジショニング：差別化と採算性');

// Left: Differentiation
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 1.3, w: 4.3, h: 2.8,
  fill: { color: colors.lightGray }, line: { color: colors.orange, width: 2 }
});

slide.addText('競争優位性', {
  x: 0.7, y: 1.45, w: 4, h: 0.25,
  fontSize: 14, bold: true, color: colors.orange, fontFace: 'Arial'
});

const diffPoints = [
  '✓ 小規模案件専門',
  '✓ 段階的営業フロー',
  '✓ 沖縄特化営業',
  '✓ 信頼構築3-6ヶ月',
  '✓ 成約率40-60%'
];

let diffY = 1.85;
diffPoints.forEach(pt => {
  slide.addText(pt, {
    x: 0.7, y: diffY, w: 4, h: 0.25,
    fontSize: 11, color: colors.textDark, fontFace: 'Arial'
  });
  diffY += 0.35;
});

// Right: Revenue Model
slide.addShape(pres.ShapeType.rect, {
  x: 5.2, y: 1.3, w: 4.3, h: 2.8,
  fill: { color: colors.lightGray }, line: { color: colors.navy, width: 2 }
});

slide.addText('採算モデル（1件¥1-5B案件）', {
  x: 5.4, y: 1.45, w: 4, h: 0.25,
  fontSize: 13, bold: true, color: colors.navy, fontFace: 'Arial'
});

const revenueLines = [
  '【売上A】M&A仲介手数料',
  '¥2-7M',
  '',
  '【売上B】事前診断・相談フィー',
  '¥1-2M',
  '',
  '【売上C】法人保険（3年間）',
  '¥0.5-1M/年',
  '',
  '【売上D】経営相談（継続）',
  '¥0.5M/年',
  '',
  '合計：¥6-15M/件'
];

let revY = 1.85;
revenueLines.forEach((line, idx) => {
  const isBold = line.includes('合計') || line.includes('【');
  const fontSize = isBold ? 10 : 9;
  const fontBold = isBold;
  const color = line.includes('合計') ? colors.navy : colors.textDark;

  slide.addText(line, {
    x: 5.4, y: revY, w: 4, h: 0.2,
    fontSize: fontSize, bold: fontBold, color: color, fontFace: 'Arial'
  });
  revY += 0.18;
});

// Slide 11: 9-Month Implementation Roadmap
slide = pres.addSlide();
slide.background = { color: colors.white };

addTitle(slide, '9ヶ月25-59件達成ロードマップ');

const roadmap = [
  ['期間', '営業活動', '月間新規接触', '月間成約', '累計成約'],
  ['8月', '運用開始', '月4-6社', '—', '準備'],
  ['9-10月', '初期接触 + 信頼構築', '月6-10社', '0-1件', '0-1件'],
  ['11月-1月', '段階的営業進行中', '月8-12社', '1-2件/月', '3-6件'],
  ['2-4月', '成熟期 + 新規開拓', '月12-15社', '2-3件/月', '25-59件']
];

let roadY = 1.3;
const roadCellH = 0.45;
const roadColWidths = [1.5, 2.2, 2.0, 1.8, 1.5];

roadmap.forEach((row, rowIdx) => {
  let cellX = 0.5;

  row.forEach((cell, colIdx) => {
    const cellWidth = roadColWidths[colIdx];
    const bgColor = rowIdx === 0 ? colors.navy : (rowIdx === roadmap.length - 1 ? colors.lightGray : colors.white);
    const textColor = rowIdx === 0 ? colors.white : colors.textDark;
    const fontSize = rowIdx === 0 ? 10 : 9;
    const bold = rowIdx === 0 || rowIdx === roadmap.length - 1;

    slide.addShape(pres.ShapeType.rect, {
      x: cellX, y: roadY, w: cellWidth, h: roadCellH,
      fill: { color: bgColor }, line: { color: colors.navy, width: 1 }
    });

    slide.addText(cell, {
      x: cellX + 0.05, y: roadY, w: cellWidth - 0.1, h: roadCellH,
      fontSize: fontSize, bold: bold, color: textColor, align: 'center', valign: 'middle', fontFace: 'Arial'
    });

    cellX += cellWidth;
  });

  roadY += roadCellH;
});

// Key drivers
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 4.0, w: 9, h: 1.3,
  fill: { color: colors.lightGray }, line: { color: colors.orange, width: 1 }
});

slide.addText('実現を支える3つの要素', {
  x: 0.7, y: 4.1, w: 8.6, h: 0.2,
  fontSize: 12, bold: true, color: colors.orange, fontFace: 'Arial'
});

const drivers = [
  '1. 段階的営業フロー：DM→電話→訪問→関係構築→M&A提案（成約率40-60%）',
  '2. 3チャネル統合：補助金情報（サイト）+ 訪問営業 + 紹介ルート',
  '3. データドリブン：案件スコアリング + 業界別アプローチ最適化'
];

let drvY = 4.35;
drivers.forEach(drv => {
  slide.addText(drv, {
    x: 0.7, y: drvY, w: 8.6, h: 0.25,
    fontSize: 10, color: colors.textDark, fontFace: 'Arial'
  });
  drvY += 0.27;
});

// Slide 12: Conclusion
slide = pres.addSlide();
slide.background = { color: colors.white };

slide.addText('結論：経営判断ポイント', {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 36, bold: true, color: colors.orange, align: 'left', fontFace: 'Arial'
});

// Left side: Market points
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 1.1, w: 4.3, h: 3.8,
  fill: { color: colors.lightGray }, line: { color: colors.orange, width: 2 }
});

slide.addText('市場機会のポイント', {
  x: 0.7, y: 1.25, w: 4, h: 0.25,
  fontSize: 13, bold: true, color: colors.orange, fontFace: 'Arial'
});

const marketPoints = [
  '✓ 後継者不安4,000社',
  '✓ 年間成約120-150件',
  '✓ 成約率わずか2-3%',
  '✓ 年間成長+50%',
  '✓ 未開拓市場¥200B+',
  '',
  '既存業者は採算性で小規模対応が不可',
  '←GLOWはビジネスモデルで解決'
];

let mktY = 1.65;
marketPoints.forEach(pt => {
  slide.addText(pt, {
    x: 0.7, y: mktY, w: 3.8, h: 0.25,
    fontSize: 10, color: pt.includes('←') ? colors.navy : colors.textDark, bold: pt.includes('←'), fontFace: 'Arial'
  });
  mktY += 0.28;
});

// Right side: Investment decision
slide.addShape(pres.ShapeType.rect, {
  x: 5.2, y: 1.1, w: 4.3, h: 3.8,
  fill: { color: colors.navy }, line: { color: colors.navy, width: 0 }
});

slide.addText('投資判断ポイント', {
  x: 5.4, y: 1.25, w: 4, h: 0.25,
  fontSize: 13, bold: true, color: colors.white, fontFace: 'Arial'
});

const investPoints = [
  '■ 沖縄特有リスクは対策可能',
  '  文化理解 + 段階的営業',
  '',
  '■ 経営者心理が明確',
  '  決断トリガー事前把握',
  '',
  '■ 採算モデルが実装可能',
  '  小規模×複数柱で利益確保',
  '',
  '■ 9ヶ月25-59件の根拠明確',
  '  段階的営業×3チャネル'
];

let invY = 1.65;
investPoints.forEach(pt => {
  const fontSize = pt.includes('■') ? 11 : 10;
  const bold = pt.includes('■');
  slide.addText(pt, {
    x: 5.4, y: invY, w: 4, h: 0.2,
    fontSize: fontSize, bold: bold, color: colors.white, fontFace: 'Arial'
  });
  invY += 0.25;
});

// Decision box
slide.addShape(pres.ShapeType.rect, {
  x: 0.5, y: 5.05, w: 9, h: 0.4,
  fill: { color: colors.orange }, line: { color: colors.orange, width: 0 }
});

slide.addText('結論：GO / NO-GO の経営判断', {
  x: 0.7, y: 5.1, w: 8.6, h: 0.3,
  fontSize: 16, bold: true, color: colors.white, align: 'center', fontFace: 'Arial'
});

// Save
pres.writeFile({ fileName: '/tmp/okinawa_ma_executive.pptx' });
console.log('Created: /tmp/okinawa_ma_executive.pptx');
