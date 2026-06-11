import React from "react";

export default function Slider({ name, value, min, max, step, onChange, format, hint }) {
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <div className="slider-row">
      <div className="slider-head">
        <span className="name">{name}</span>
        <span className="val">{format ? format(value) : value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={{ "--fill": `${fill}%` }}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {hint && <div className="slider-hint">{hint}</div>}
    </div>
  );
}
