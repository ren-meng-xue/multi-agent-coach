"use client";

import React from "react";
import { type DashboardData } from "@/lib/user";

/** 渲染个人仪表盘页面内容。 */
export function DashboardContent({ data }: { data: DashboardData }) {
  const {
    session_count,
    total_duration_hours,
    average_score,
    weaknesses_improved_count,
    radar,
    growth_trajectory,
    weaknesses
  } = data;

  // 雷达图计算：中心 (150, 150)，最大半径 100 (对应 10 分)
  const getRadarPoint = (score: number, angleDeg: number) => {
    const r = (score / 10) * 100;
    const angleRad = (angleDeg - 90) * (Math.PI / 180);
    const x = 150 + r * Math.cos(angleRad);
    const y = 150 + r * Math.sin(angleRad);
    return `${x},${y}`;
  };

  const radarPoints = [
    getRadarPoint(radar.structure, 0),      // Top
    getRadarPoint(radar.technical_depth, 90), // Right
    getRadarPoint(radar.quantified_results, 180), // Bottom
    getRadarPoint(radar.failure_tradeoffs, 270), // Left
  ].join(" ");

  // 成长轨迹计算：x 从 60 到 380，y 从 150 (0分) 到 30 (10分)
  const getGrowthPoints = () => {
    if (growth_trajectory.length === 0) return "";
    return growth_trajectory.map((p, i) => {
      const x = 60 + (i * (320 / Math.max(1, growth_trajectory.length - 1)));
      const y = 150 - (p.score / 10) * 120;
      return { x, y, score: p.score, label: `#${p.session_index}` };
    });
  };

  const gPoints = getGrowthPoints();
  const polylinePoints = typeof gPoints === "string" ? "" : gPoints.map(p => `${p.x},${p.y}`).join(" ");
  const areaPoints = typeof gPoints === "string" ? "" : `60,170 ${polylinePoints} 380,170`;

  // 格式化时长显示：小于 60min 显示为 min，否则显示为 h
  const formatDuration = (hours: number) => {
    const minutes = Math.round(hours * 60);
    if (minutes < 60) {
      return { num: minutes, unit: "min" };
    }
    return { num: hours, unit: "h" };
  };

  const duration = formatDuration(total_duration_hours);

  return (
    <div className="w-full max-w-[1200px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* 1. 统计卡片行 */}
      <div className="mac-stat-row-cards">
        <div className="mac-stat-card c1">
          <div className="num">{session_count}</div>
          <div className="lbl">总练习场次</div>
        </div>
        <div className="mac-stat-card c2">
          <div className="num">
            {duration.num}
            <span className="text-[0.4em] ml-0.5 font-normal">{duration.unit}</span>
          </div>
          <div className="lbl">累计练习时长</div>
        </div>
        <div className="mac-stat-card c3">
          <div className="num">{average_score}</div>
          <div className="lbl">平均综合评分</div>
        </div>
        <div className="mac-stat-card c4">
          <div className="num">{weaknesses_improved_count}</div>
          <div className="lbl">弱点项已改善</div>
        </div>
      </div>

      {/* 2. 图表双列 */}
      <div className="mac-chart-duo">
        <div className="mac-chart-box">
          <h4>能力雷达 (近 5 场)</h4>
          <svg viewBox="0 0 300 300" className="w-full max-w-[340px] block mx-auto">
            {/* 雷达图背景网格 */}
            {[10, 7.5, 5, 2.5].map(score => {
              const pts = [0, 90, 180, 270].map(a => getRadarPoint(score, a)).join(" ");
              return <polygon key={score} points={pts} fill="none" stroke="#e8e7e2" strokeWidth="1" />;
            })}
            
            {/* 轴线 */}
            <line x1="150" y1="50" x2="150" y2="250" stroke="#e8e7e2" strokeWidth="1" />
            <line x1="50" y1="150" x2="250" y2="150" stroke="#e8e7e2" strokeWidth="1" />
            
            {/* 数据区域 */}
            <polygon 
              points={radarPoints} 
              fill="rgba(79,70,229,0.12)" 
              stroke="#4f46e5" 
              strokeWidth="2.5" 
            />
            
            {/* 数据点 */}
            {radarPoints.split(" ").map((pt, i) => {
              const [cx, cy] = pt.split(",");
              return <circle key={i} cx={cx} cy={cy} r="4.5" fill="#4f46e5" />;
            })}
            
            {/* 文字标签 */}
            <text x="150" y="35" textAnchor="middle" fill="#8a8a8a" fontSize="10" className="font-sans">Structure 结构性</text>
            <text x="260" y="153" textAnchor="start" fill="#8a8a8a" fontSize="10" className="font-sans">Depth 深度</text>
            <text x="150" y="275" textAnchor="middle" fill="#8a8a8a" fontSize="10" className="font-sans">Results 结果量化</text>
            <text x="40" y="153" textAnchor="end" fill="#8a8a8a" fontSize="10" className="font-sans">Tradeoffs 权衡</text>
          </svg>
        </div>

        <div className="mac-chart-box">
          <h4>成长轨迹（近 10 场）</h4>
          <svg viewBox="0 0 400 200" className="w-full">
            {/* 背景参考线 */}
            {[30, 60, 90, 120, 150].map(y => (
              <line key={y} x1="50" y1={y} x2="380" y2={y} stroke="#e8e7e2" strokeWidth="1" />
            ))}
            
            {/* 纵轴标签 */}
            <text x="42" y="34" textAnchor="end" fill="#8a8a8a" fontSize="10">10</text>
            <text x="42" y="94" textAnchor="end" fill="#8a8a8a" fontSize="10">6</text>
            <text x="42" y="154" textAnchor="end" fill="#8a8a8a" fontSize="10">2</text>
            
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.12" />
                <stop offset="100%" stopColor="#4f46e5" stopOpacity="0" />
              </linearGradient>
            </defs>
            
            {/* 面积填充 */}
            {areaPoints && <polygon points={areaPoints} fill="url(#areaGrad)" />}
            
            {/* 折线 */}
            {polylinePoints && (
              <polyline 
                points={polylinePoints}
                fill="none" 
                stroke="#4f46e5" 
                strokeWidth="2.5" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
              />
            )}
            
            {/* 数据点 */}
            {Array.isArray(gPoints) && gPoints.map((p, i) => (
              <circle 
                key={i} 
                cx={p.x} 
                cy={p.y} 
                r={i === gPoints.length - 1 ? 5 : 3} 
                fill={i === gPoints.length - 1 ? "#fff" : "#4f46e5"} 
                stroke={i === gPoints.length - 1 ? "#4f46e5" : "none"}
                strokeWidth={i === gPoints.length - 1 ? 2.5 : 0}
              />
            ))}
            
            {/* 横轴标签 */}
            {Array.isArray(gPoints) && gPoints.filter((_, i) => i % 3 === 0 || i === gPoints.length - 1).map((p, i) => (
              <text 
                key={i} 
                x={p.x} 
                y="172" 
                textAnchor="middle" 
                fill={p.label.includes(session_count.toString()) ? "#4f46e5" : "#8a8a8a"} 
                fontSize="9"
                fontWeight={p.label.includes(session_count.toString()) ? "600" : "400"}
              >
                {p.label}
              </text>
            ))}
          </svg>
        </div>
      </div>

      {/* 3. 标签云 */}
      <div className="mac-tag-cloud-box">
        <h4>当前薄弱项</h4>
        <div className="mac-tag-cluster">
          {weaknesses.length > 0 ? (
            weaknesses.map((w, i) => (
              <span key={i} className={`mac-tag-pill ${w.severity}`}>{w.tag}</span>
            ))
          ) : (
            <div className="text-gray-400 text-sm py-4">暂无薄弱项记录，完成面试后将自动生成。</div>
          )}
        </div>
      </div>
    </div>
  );
}
