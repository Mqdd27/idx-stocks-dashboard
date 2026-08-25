"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const MONTHS = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
const DAYS = ["Min","Sen","Sel","Rab","Kam","Jum","Sab"];

export default function CalendarPage() {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [days, setDays] = useState<any[]>([]);
  const [holidays, setHolidays] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [error, setError] = useState(false);
  const [year, monthNumber] = month.split("-").map(Number);
  const holidayMap = useMemo(() => new Map(holidays.map((h) => [h.date, h])), [holidays]);

  useEffect(() => {
    const start = `${month}-01`;
    const end = `${month}-${new Date(year, monthNumber, 0).getDate()}`;
    Promise.all([api.marketCalendar(start, end), api.marketHolidays(), api.marketEvents(start, end)])
      .then(([calendar, holidayRows, eventRows]) => { setDays(calendar.data || []); setHolidays(holidayRows.data || []); setEvents(eventRows.data || []); setError(false); })
      .catch(() => setError(true));
  }, [month, year, monthNumber]);

  const changeMonth = (delta: number) => {
    let nextYear = year;
    let nextMonth = monthNumber + delta;
    if (nextMonth < 1) { nextMonth = 12; nextYear -= 1; }
    if (nextMonth > 12) { nextMonth = 1; nextYear += 1; }
    setMonth(nextYear + "-" + String(nextMonth).padStart(2, "0"));
  };
  const firstDay = new Date(year, monthNumber - 1, 1).getDay();
  const cells = [...Array(firstDay).fill(null), ...days];
  while (cells.length % 7) cells.push(null);

  return <div className="calendar-page">
    <div className="calendar-heading"><div><h1 className="page-title">Market Calendar</h1><p className="muted">Jadwal perdagangan IDX · Asia/Jakarta</p></div><div className="calendar-controls"><button type="button" className="btn btn-sm" onClick={() => changeMonth(-1)}>‹</button><strong>{MONTHS[monthNumber - 1]} {year}</strong><button type="button" className="btn btn-sm" onClick={() => changeMonth(1)}>›</button></div></div>
    {error ? <div className="empty-state">Gagal memuat kalender.</div> : <>
      <div className="calendar-sheet">
        <div className="calendar-sheet-title">{MONTHS[monthNumber - 1]} {year}</div>
        <div className="calendar-weekdays">{DAYS.map((d, i) => <div key={d} className={i === 0 ? "sunday" : ""}>{d}</div>)}</div>
        <div className="calendar-month-grid">{cells.map((day, i) => {
          if (!day) return <div className="calendar-cell empty" key={`empty-${i}`} />;
          const holiday = holidayMap.get(day.date); const dayEvents = events.filter((e) => e.date === day.date); const weekend = i % 7 === 0;
          const closed = !day.is_trading_day; const title = holiday?.name || dayEvents.map((e) => `${e.action_type}: ${e.symbol}`).join(" · ") || (weekend ? "Weekend" : closed ? "Market closed" : "Trading day");
          return <div className={`calendar-cell ${closed ? "holiday" : "trading"} ${weekend ? "sunday" : ""}`} key={day.date} title={title}><div className="calendar-date">{Number(day.date.slice(-2))}</div><div className="calendar-mark">{holiday ? "Holiday" : dayEvents.length ? "Event" : day.is_trading_day ? "Open" : "Closed"}</div><div className="calendar-tooltip"><b>{day.date}</b><strong>{title}</strong>{holiday && <span>{holiday.holiday_type}</span>}{dayEvents.map((e) => <span key={e.symbol + e.action_type}>{e.symbol} · {e.action_type}</span>)}</div></div>;
        })}</div>
        <div className="calendar-legend"><span><i className="legend-dot open" />Trading day</span><span><i className="legend-dot red" />Holiday / closed</span><span><i className="legend-dot event" />Corporate action / IPO</span></div>
      </div>
      <div className="card calendar-sessions"><div className="card-title">IDX Trading Sessions</div><div className="session-list"><span>Pre-open 08:45–09:00</span><span>Session 1 09:00–12:00</span><span>Break 12:00–13:30</span><span>Session 2 13:30–15:50</span><span>Post-market 15:50–16:00</span></div></div>
    </>}
  </div>;
}
