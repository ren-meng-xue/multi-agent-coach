"use client";

import React from "react";

/** 渲染个人仪表盘页面内容。 */
export function DashboardContent({ 
  sessionCount = 37, 
  passRate = 33 
}: { 
  sessionCount?: number; 
  passRate?: number;
}) {
  return (
    <div className="w-full max-w-[1200px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* 1. 统计卡片行 */}
      <div className="mac-stat-row-cards">
        <div className="mac-stat-card c1">
          <div className="num">{sessionCount}</div>
          <div className="lbl">总练习场次</div>
        </div>
        <div className="mac-stat-card c2">
          <div className="num">18.5h</div>
          <div className="lbl">累计练习时长</div>
        </div>
        <div className="mac-stat-card c3">
          <div className="num">7.2</div>
          <div className="lbl">平均综合评分</div>
        </div>
        <div className="mac-stat-card c4">
          <div className="num">12</div>
          <div className="lbl">弱点项已改善</div>
        </div>
      </div>

      {/* 2. 图表双列 */}
      <div className="mac-chart-duo">
        <div className="mac-chart-box">
          <h4>能力雷达</h4>
          <svg viewBox="0 0 300 300" className="w-full max-w-[340px] block mx-auto">
            {/* 雷达图背景网格 */}
            <polygon points="150,40 252,115 235,230 65,230 48,115" fill="none" stroke="#e8e7e2" strokeWidth="1" />
            <polygon points="150,73 230,125 218,206 82,206 70,125" fill="none" stroke="#e8e7e2" strokeWidth="1" />
            <polygon points="150,106 208,135 201,182 99,182 92,135" fill="none" stroke="#e8e7e2" strokeWidth="1" />
            
            {/* 轴线 */}
            <line x1="150" y1="150" x2="150" y2="40" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="150" y1="150" x2="252" y2="115" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="150" y1="150" x2="235" y2="230" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="150" y1="150" x2="65" y2="230" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="150" y1="150" x2="48" y2="115" stroke="#e8e7e2" strokeWidth="1" />
            
            {/* 数据区域 */}
            <polygon 
              points="150,62 208,128 205,186 108,198 78,128" 
              fill="rgba(79,70,229,0.12)" 
              stroke="#4f46e5" 
              strokeWidth="2.5" 
            />
            
            {/* 数据点 */}
            <circle cx="150" cy="62" r="4.5" fill="#4f46e5" />
            <circle cx="208" cy="128" r="4.5" fill="#4f46e5" />
            <circle cx="205" cy="186" r="4.5" fill="#4f46e5" />
            <circle cx="108" cy="198" r="4.5" fill="#4f46e5" />
            <circle cx="78" cy="128" r="4.5" fill="#4f46e5" />
            
            {/* 文字标签 */}
            <text x="150" y="28" textAnchor="middle" fill="#8a8a8a" fontSize="10" className="font-sans">Clarity 清晰度</text>
            <text x="260" y="115" textAnchor="start" fill="#8a8a8a" fontSize="10" className="font-sans">Depth 深度</text>
            <text x="240" y="248" textAnchor="middle" fill="#8a8a8a" fontSize="10" className="font-sans">Specificity 具体性</text>
            <text x="60" y="248" textAnchor="middle" fill="#8a8a8a" fontSize="10" className="font-sans">STAR 完整性</text>
          </svg>
        </div>

        <div className="mac-chart-box">
          <h4>成长轨迹（近 10 场）</h4>
          <svg viewBox="0 0 400 200" className="w-full">
            {/* 背景参考线 */}
            <line x1="50" y1="30" x2="380" y2="30" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="50" y1="60" x2="380" y2="60" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="50" y1="90" x2="380" y2="90" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="50" y1="120" x2="380" y2="120" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="50" y1="150" x2="380" y2="150" stroke="#e8e7e2" strokeWidth="1" />
            
            {/* 纵轴标签 */}
            <text x="42" y="34" textAnchor="end" fill="#8a8a8a" fontSize="10">10</text>
            <text x="42" y="64" textAnchor="end" fill="#8a8a8a" fontSize="10">8</text>
            <text x="42" y="94" textAnchor="end" fill="#8a8a8a" fontSize="10">6</text>
            <text x="42" y="124" textAnchor="end" fill="#8a8a8a" fontSize="10">4</text>
            <text x="42" y="154" textAnchor="end" fill="#8a8a8a" fontSize="10">2</text>
            
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.12" />
                <stop offset="100%" stopColor="#4f46e5" stopOpacity="0" />
              </linearGradient>
            </defs>
            
            {/* 面积填充 */}
            <polygon 
              points="60,150 96,135 132,135 168,120 204,135 240,105 276,105 312,90 348,105 380,90 380,170 60,170" 
              fill="url(#areaGrad)" 
            />
            
            {/* 折线 */}
            <polyline 
              points="60,150 96,135 132,135 168,120 204,135 240,105 276,105 312,90 348,105 380,90"
              fill="none" 
              stroke="#4f46e5" 
              strokeWidth="2.5" 
              strokeLinecap="round" 
              strokeLinejoin="round" 
            />
            
            {/* 数据点 */}
            <circle cx="60" cy="150" r="3" fill="#4f46e5" />
            <circle cx="96" cy="135" r="3" fill="#4f46e5" />
            <circle cx="132" cy="135" r="3" fill="#4f46e5" />
            <circle cx="168" cy="120" r="3" fill="#4f46e5" />
            <circle cx="204" cy="135" r="3" fill="#4f46e5" />
            <circle cx="240" cy="105" r="3" fill="#4f46e5" />
            <circle cx="276" cy="105" r="3" fill="#4f46e5" />
            <circle cx="312" cy="90" r="3" fill="#4f46e5" />
            <circle cx="348" cy="105" r="3" fill="#4f46e5" />
            <circle cx="380" cy="90" r="5" fill="#fff" stroke="#4f46e5" strokeWidth="2.5" />
            
            {/* 横轴标签 */}
            <text x="60" y="172" textAnchor="middle" fill="#8a8a8a" fontSize="9">#1</text>
            <text x="168" y="172" textAnchor="middle" fill="#8a8a8a" fontSize="9">#4</text>
            <text x="276" y="172" textAnchor="middle" fill="#8a8a8a" fontSize="9">#7</text>
            <text x="380" y="172" textAnchor="middle" fill="#4f46e5" fontSize="9" fontWeight="600">#10</text>
          </svg>
        </div>
      </div>

      {/* 3. 标签云 */}
      <div className="mac-tag-cloud-box">
        <h4>当前薄弱项</h4>
        <div className="mac-tag-cluster">
          <span className="mac-tag-pill severe">系统设计·高并发</span>
          <span className="mac-tag-pill severe">量化结果表述</span>
          <span className="mac-tag-pill warn">STAR 完整性</span>
          <span className="mac-tag-pill warn">反问环节准备</span>
          <span className="mac-tag-pill info">RAG 评估指标</span>
          <span className="mac-tag-pill info">LangGraph Checkpoint</span>
          <span className="mac-tag-pill warn">技术深度不足</span>
        </div>
      </div>
    </div>
  );
}
