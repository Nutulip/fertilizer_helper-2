"""Consolidate Module 4's Tab-4 render into a single summary dashboard."""
import io
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "index.html"
s = io.open(P, encoding="utf-8").read()
lines = s.split("\n")

# Replace lines 1529..1611 (1-indexed): the `const marks` line through the
# closing renderGates call of the Tab 4 result block.
start = next(i for i, l in enumerate(lines) if "const marks = [10, 20, 30, 40];" in l)
end = next(i for i, l in enumerate(lines[start:], start)
           if "renderGates(r.gates)" in l)

NEW = r"""    const caseTone = d.is_wash_anomaly ? 'border-red-500 bg-red-50'
                   : d.wash_required ? 'border-amber-400 bg-amber-50'
                   : 'border-slate-200 bg-slate-50';

    $('out4').innerHTML =
      card('Irrigation & Leaching Summary', '灌溉与排液比综合看板', `
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div class="rounded-lg border-2 border-slate-200 bg-slate-50 p-3">
            <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">
              ${esc(d.leaching_fraction_text)}</p>
            <p class="mt-1 text-3xl font-bold tabular-nums ${lfTone}">
              ${fmt(d.leaching_fraction_pct, 1)}<span class="text-base">%</span></p>
            <p class="mt-0.5 text-[11px] font-semibold text-slate-600">${esc(d.band_text)}</p>
          </div>
          <div class="rounded-lg border-2 ${d.wash_required ? 'border-red-400 bg-red-50' : 'border-slate-200 bg-slate-50'} p-3">
            <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">
              ${esc(d.delta_ec_text)}</p>
            <p class="mt-1 text-3xl font-bold tabular-nums ${dTone}">${fmt(d.delta_ec_ms_cm, 2)}</p>
            <p class="mt-0.5 text-[11px] font-semibold text-slate-600">${esc(d.wash_required_text)}</p>
          </div>
          <div class="rounded-lg border-2 border-slate-200 bg-slate-50 p-3">
            <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">
              Irrigation / Drain (灌溉 / 排液)</p>
            <p class="mt-1 text-2xl font-bold tabular-nums text-slate-700">
              ${fmt(d.used_irrigation_l_m2, 2)}<span class="text-sm font-normal"> / ${fmt(d.drain_l_m2, 2)}</span></p>
            <p class="mt-0.5 text-[11px] text-slate-500">L/m² · uptake ${fmt(d.uptake_l_m2, 2)} (吸水量)</p>
            ${d.is_estimated_volume ? `<p class="mt-1 text-[10px] font-semibold text-amber-800 bg-amber-100 rounded px-1.5 py-0.5 inline-block">${esc(d.is_estimated_volume_text)}</p>` : ''}
          </div>
          <div class="rounded-lg border-2 ${caseTone} p-3">
            <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">
              Wash Strategy (冲洗策略)</p>
            <p class="mt-1 text-sm font-bold text-slate-800 leading-snug">${esc(d.wash_case_text)}</p>
            ${d.wash_required ? `<p class="mt-1 text-[11px] text-slate-600">Target LF ${fmt(d.target_lf_pct, 1)}% (目标排液比)</p>` : ''}
          </div>
        </div>

        <div class="mt-4">
          <div class="relative h-7 bg-gradient-to-r from-amber-200 via-emerald-200 to-amber-200 rounded-lg overflow-hidden">
            <div class="absolute inset-y-0 bg-brand-700 w-1" style="left:${Math.min(99, d.leaching_fraction_pct)}%"></div>
            ${[10, 20, 30, 40].map(m => `<div class="absolute inset-y-0 border-l border-white/70" style="left:${m}%"></div>`).join('')}
          </div>
          <div class="flex justify-between text-[10px] text-slate-400 mt-1">
            <span>0%</span><span>10%</span><span>20%</span><span>30%</span><span>40%</span><span>50%+</span>
          </div>
        </div>

        ${d.wash_required ? (d.is_wash_anomaly ? `
        <div class="mt-4 rounded-xl border-2 border-red-500 bg-red-50 p-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs font-bold px-2 py-1 rounded bg-red-600 text-white">⛔ G-WASH-ANOMALY</span>
            <span class="text-xs font-semibold text-red-900">${esc(d.wash_anomaly_text)}</span>
          </div>
          <p class="mt-2 text-sm font-bold text-red-800">
            Extra Irrigation Needed (需增加灌溉量):
            <span class="font-mono">${esc(d.extra_irrigation_display)}</span></p>
          <p class="mt-1 text-[11px] text-red-700 leading-snug">
            Leaching fraction is already ${fmt(d.leaching_fraction_pct, 1)}% — adding volume wastes
            water and fertiliser without closing the EC gap.
            <span class="block">（排液比已达 ${fmt(d.leaching_fraction_pct, 1)}%，继续加水只会浪费水肥，且无法缩小电导差。）</span></p>
        </div>` : `
        <div class="mt-4 rounded-xl border-2 border-amber-500 bg-gradient-to-br from-amber-50 to-red-50 p-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs font-bold px-2 py-1 rounded bg-red-600 text-white">⚡ G-WASH-TRIGGER</span>
            <span class="text-xs font-semibold text-amber-900">${esc(d.wash_case_text)}</span>
          </div>
          <div class="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div class="rounded-lg bg-white/80 border border-amber-300 p-3">
              <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Current (当前灌溉量)</p>
              <p class="mt-1 text-2xl font-bold tabular-nums text-slate-700">
                ${fmt(d.used_irrigation_l_m2, 2)}<span class="text-sm font-normal"> L/m²</span></p>
            </div>
            <div class="rounded-lg bg-white border-2 border-red-400 p-3">
              <p class="text-[11px] uppercase tracking-wide text-red-700 font-semibold">Extra Needed (需增加灌溉量)</p>
              <p class="mt-1 text-3xl font-black tabular-nums text-red-700">
                +${fmt(d.extra_irrigation_l_m2, 2)}<span class="text-sm font-normal"> L/m²</span></p>
              <p class="mt-0.5 text-[10px] text-slate-500">per day (每日)</p>
            </div>
            <div class="rounded-lg bg-white/80 border border-amber-300 p-3">
              <p class="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Target (目标灌溉量)</p>
              <p class="mt-1 text-2xl font-bold tabular-nums text-emerald-700">
                ${fmt(d.target_irrigation_l_m2, 2)}<span class="text-sm font-normal"> L/m²</span></p>
              <p class="mt-0.5 text-[10px] text-slate-500">→ LF ${fmt(d.target_lf_pct, 1)}%</p>
            </div>
          </div>
          ${d.is_estimated_volume ? `<p class="mt-3 text-[11px] text-amber-900 bg-amber-100 border border-amber-300 rounded-lg p-2 leading-snug"><span class="font-bold">⚠</span> Irrigation volume was not supplied; a crop-stage reference of ${fmt(d.used_irrigation_l_m2, 2)} L/m²/day was used. Verify against your metering.<span class="block text-amber-700">（未提供灌溉量，已采用作物阶段参考值估算，请与实际计量核对。）</span></p>` : ''}
          <p class="mt-2 text-[10px] font-mono text-slate-500">${esc(d.formula_extra_text)}</p>
        </div>`) : ''}

        <p class="mt-3 text-[11px] font-mono text-slate-500 bg-slate-50 rounded p-2">${esc(d.formula_text)}</p>
        <p class="mt-2 text-[11px] text-amber-700">${esc(d.provenance_text)}</p>
      `) + '<div class="mt-5">' + renderGates(r.gates) + '</div>';"""

lines[start:end + 1] = NEW.split("\n")
io.open(P, "w", encoding="utf-8").write("\n".join(lines))
print(f"replaced lines {start + 1}..{end + 1} with {len(NEW.splitlines())} lines")
