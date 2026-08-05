import type { MatchReport } from "../types";

/**
 * 对照标尺：能力实心、呈现空心，两者之差用琥珀斜纹标出。
 * 差距 = 能力下界 − 呈现上界，只有真的存在差距时才画那条斜纹。
 */
export function GapGauge({ report, requirementText }: { report: MatchReport; requirementText: (id: string) => string }) {
  const recoverable = Math.max(0, report.capability_low - report.presentation_high);

  return (
    <section className="gauge" aria-labelledby="gauge-title">
      <p className="eyebrow">对照标尺</p>
      <h2 id="gauge-title">你能做什么，和简历写了什么</h2>

      <div className="gauge-track">
        <Bar
          metric="capability"
          name="岗位能力适配度"
          low={report.capability_low}
          high={report.capability_high}
        />
        <Bar
          metric="presentation"
          name="当前简历呈现度"
          low={report.presentation_low}
          high={report.presentation_high}
        />

        {/* 斜纹带按真实位置画：从呈现上界到能力下界，就是那段空着的距离。 */}
        {recoverable > 0 && (
          <div className="gauge-row gauge-delta" role="group" aria-label="改写可补">
            <span className="gauge-name">改写可补</span>
            <span className="gauge-lane">
              <span
                className="gauge-hatch"
                style={{
                  left: `${report.presentation_high}%`,
                  width: `${recoverable}%`,
                }}
                aria-hidden="true"
              />
            </span>
            <span className="gauge-value">{recoverable} 分</span>
          </div>
        )}

        <div className="gauge-row gauge-axis" aria-hidden="true">
          <span />
          <span className="gauge-lane gauge-ticks">
            <span>0</span>
            <span>50</span>
            <span>100</span>
          </span>
          <span />
        </div>
      </div>

      <p className="hint">
        分析置信度 {report.confidence}。这两条不是同一件事：上面一条是你的真实经历撑得起多少，
        下面一条是简历眼下讲出来了多少。
        {recoverable > 0
          ? "中间那段琥珀色，改写简历就能补回来，不需要新增任何经历。"
          : "两条基本齐平，简历已经把你的经历讲清楚了。"}
      </p>
      <p className="hint">匹配度不代表 ATS 通过率、面试概率或录用概率。</p>

      {report.hard_gate_risks.length > 0 && (
        <div className="gate-stamps">
          <p className="eyebrow">硬性门槛 · 不计入上面的分数</p>
          {report.hard_gate_risks.map((id) => (
            <span key={id} className="gate-stamp">
              {requirementText(id)}
            </span>
          ))}
          <p className="hint">
            这类条件可能直接筛人，所以单独列出，不让它被其他维度的高分平均掉。
          </p>
        </div>
      )}
    </section>
  );
}

function Bar({
  metric,
  name,
  low,
  high,
}: {
  metric: "capability" | "presentation";
  name: string;
  low: number;
  high: number;
}) {
  return (
    <div className="gauge-row" role="group" aria-label={name}>
      <span className="gauge-name">{name}</span>
      <span className="gauge-lane gauge-bar">
        <span
          className="gauge-fill"
          data-metric={metric}
          style={{ left: `${low}%`, width: `${Math.max(high - low, 1.5)}%` }}
        />
      </span>
      <span className="gauge-value">{`${low}–${high}`}</span>
    </div>
  );
}
