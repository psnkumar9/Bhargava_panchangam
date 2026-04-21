function formatEngineEventList(items){
  if(!items || !items.length) return 'None on this day';
  return items.map(item =>
    `${item.display}<br><span style="font-size:0.68rem;color:#FFCC88;">${item.nakshatra}</span>`
  ).join('<br>');
}

function betaPendingNote(text){
  return `${text}<br><span style="font-size:0.68rem;color:#FFCC88;">Closed-group validation</span>`;
}

function withValidationNote(html){
  return `${html}<br><span style="font-size:0.68rem;color:#FFCC88;">Validation in progress</span>`;
}

function formatSameDayEntries(entries){
  if(!entries || !entries.length) return '--';
  return entries.map((item, index) =>
    `<div style="padding:4px 0;${index ? 'border-top:1px solid rgba(255,215,0,0.12);margin-top:4px;' : ''}">${item.name}<br><span style="font-size:0.68rem;color:#FFCC88;">till ${item.end_display}</span></div>`
  ).join('<br>');
}

let latestTimelinePayload = null;

function renderSlots(container, startH, slotMinutes, dow, nowH, isNight){
  let html='';
  for(let i=0;i<30;i++){
    const t0=startH+i*slotMinutes/60;
    const t1=t0+slotMinutes/60;
    const result=BHARGAV[i][dow];
    const cat=getCategory(result);
    const isNow=nowH>=t0&&nowH<t1;
    html+=`<div class="slot${isNow?' now':''}${isNight?' night-slot':''}">
      <div class="time">${hToTime(t0)}<br><small style="font-size:0.65rem;opacity:0.7;">to ${hToTime(t1)}</small></div>
      <div class="result ${cat}">${result}${isNow?'<span class="now-badge">NOW</span>':''}</div>
    </div>`;
  }
  container.innerHTML=html;
}

function formatTimelineRows(items){
  if(!items || !items.length) return '<div class="timeline-empty">No values available for this day.</div>';
  return items.map(item => `
    <div class="timeline-row">
      <div class="timeline-time">${item.display}</div>
      <div class="timeline-name">${item.name}</div>
    </div>
  `).join('');
}

function openTimelineModal(kind){
  if(!latestTimelinePayload) return;
  const timelines = latestTimelinePayload.timelines || {};
  const titleMap = {
    hora: 'Hora Windows',
    lagna: 'Lagna Windows',
  };
  const body = document.getElementById('timelineModalBody');
  const title = document.getElementById('timelineModalTitle');
  title.textContent = titleMap[kind] || 'Time Windows';
  body.innerHTML = `
    <div class="timeline-note">Exact engine-derived time windows for the selected date and place.</div>
    ${formatTimelineRows(timelines[kind])}
  `;
  document.getElementById('timelineModal').style.display = 'flex';
}

function closeTimelineModal(event){
  if(event && event.target && event.target !== document.getElementById('timelineModal')) return;
  document.getElementById('timelineModal').style.display = 'none';
}

async function calculate(){
  clearErr();
  document.getElementById('results').style.display='none';

  const raw = document.getElementById('dateInput').value;
  const parsedDate = parseDisplayDate(raw);
  if(!parsedDate){
    showErr('Invalid date. Use DD-MM-YYYY, DD/MM/YYYY or DDMMYYYY');
    return;
  }

  const {day, month, year} = parsedDate;
  const testDate = new Date(year, month - 1, day);
  if(testDate.getFullYear() !== year || testDate.getMonth() !== month - 1 || testDate.getDate() !== day){
    showErr('Invalid date.');
    return;
  }
  const timeValue=(document.getElementById('timeInput')?.value||'').trim();
  if(timeValue && !/^\d{2}:\d{2}$/.test(timeValue)){
    showErr('Invalid time. Use HH:MM.');
    return;
  }

  const sel = document.getElementById('placeSelect');
  let lat, lon, tz, placeName;
  if(sel.value === 'gps' && gpsLat !== null){
    lat = gpsLat;
    lon = gpsLon;
    tz = estimateTimezone(lat, lon);
    placeName = `GPS Location (${lat.toFixed(3)}°, ${lon.toFixed(3)}°)`;
  } else if(sel.value.startsWith('saved:')){
    const c = savedLocations[+sel.value.split(':')[1]];
    if(!c){
      showErr('Saved location was not found. Please reselect it.');
      return;
    }
    lat = c.lat;
    lon = c.lon;
    tz = c.tz;
    placeName = `⭐ ${c.n}`;
  } else if(sel.value !== '' && sel.value !== 'gps'){
    const c = CITIES[+sel.value];
    lat = c.lat;
    lon = c.lon;
    tz = c.tz;
    placeName = c.n;
  } else {
    showErr('Please select a place or use GPS location.');
    return;
  }

  const dateIso = `${year}-${pad2(month)}-${pad2(day)}`;

  let payload;
  try {
    const url = `/api/panchanga?date=${encodeURIComponent(dateIso)}&time=${encodeURIComponent(timeValue || '00:00')}&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&tz=${encodeURIComponent(tz)}&timezone=${encodeURIComponent('Asia/Kolkata')}`;
    const response = await fetch(url, {cache: 'no-store'});
    payload = await response.json();
    if(!response.ok){
      throw new Error(payload.error || 'Calculation failed');
    }
  } catch (error) {
    showErr(`Calculation engine error: ${error.message}`);
    return;
  }

  const now = new Date();
  const isToday = now.getFullYear() === year && (now.getMonth() + 1) === month && now.getDate() === day;
  const nowH = isToday ? (now.getHours() + now.getMinutes() / 60) : -999;
  const daySlotMin = payload.day_length.hours * 60 / 30;
  const nightSlotMin = payload.night_length.hours * 60 / 30;
  const dow = payload.weekday.number;
  const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const pak = payload.tithi.paksha === 'Shukla' ? 'Shukla Paksha ☀️' : 'Krishna Paksha 🌙';
  const teluguTithi = TITHI_TEL[payload.tithi.number - 1] || '--';
  const durmuhurtaHtml = withValidationNote(payload.durmuhurtam.length ? payload.durmuhurtam.map(item => item.display).join('<br>') : 'None');
  const varjyamHtml = withValidationNote(formatEngineEventList(payload.varjyam));
  latestTimelinePayload = payload;

  document.getElementById('panchaInfo').innerHTML = `
    <div class="info-cell span2" style="background:rgba(255,215,0,0.08);border-color:rgba(255,215,0,0.28);">
      <div class="lbl">Closed-Group Test Build</div>
      <div class="val small" style="color:#FFD78A;">Core Panchanga fields are active for testing.</div>
      <div class="val small" style="font-size:0.74rem;color:#FFCC88;margin-top:4px;">
        Advanced muhurta fields are being verified against JHora and Drik references.
      </div>
    </div>
    <div class="info-cell span2">
      <div class="lbl">📅 Date &amp; Weekday</div>
      <div class="val gold">${String(day).padStart(2,'0')} ${MON[month - 1]} ${year}</div>
      <div class="val" style="font-size:0.82rem;color:#FFCC88;margin-top:3px;">
        ${payload.weekday.name} &nbsp;|&nbsp; ${DAYS_TEL[dow]}
      </div>
      <div class="val" style="font-size:0.74rem;color:#FFD78A;margin-top:4px;">
        Reference Time: ${payload.reference_time || (timeValue || '--')}
      </div>
    </div>
    <div class="info-cell span2">
      <div class="lbl">📍 Place (Lat: ${lat.toFixed(2)}° Lon: ${lon.toFixed(2)}°)</div>
      <div class="val small">${placeName}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Vara</div>
      <div class="val small">${payload.weekday.name}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Hora</div>
      <div class="val small">${payload.hora.ruler}<br><span style="font-size:0.68rem;color:#FFCC88;">${payload.hora.display}</span></div>
    </div>
    <div class="info-cell">
      <div class="lbl">Lagna</div>
      <div class="val small">${payload.lagna?.display || '--'}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🌄 Sunrise</div>
      <div class="val green">${payload.sunrise.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🌇 Sunset</div>
      <div class="val orange">${payload.sunset.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🕐 Day Length</div>
      <div class="val small">${payload.day_length.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🌙 Night Length</div>
      <div class="val small">${payload.night_length.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">📆 Hindu Month</div>
      <div class="val small">${payload.masa.name}${payload.masa.adhika ? ' (Adhika)' : ''}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">☀️ Surya Rasi</div>
      <div class="val small">${payload.rasi.name}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${moonEmoji(payload.tithi.number - 1)} Tithi</div>
      <div class="val small">${formatSameDayEntries(payload.tithi.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">తిథి (Telugu)</div>
      <div class="val small">${teluguTithi}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Nakshatra</div>
      <div class="val small">${formatSameDayEntries(payload.nakshatra.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Yoga</div>
      <div class="val small">${formatSameDayEntries(payload.yoga.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Karana</div>
      <div class="val small">${formatSameDayEntries(payload.karana.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Rahu Kalam</div>
      <div class="val small">${payload.rahu_kalam.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Yamagandam</div>
      <div class="val small">${payload.yamagandam.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Durmuhurtam</div>
      <div class="val small">${durmuhurtaHtml}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">Varjyam</div>
      <div class="val small">${varjyamHtml}</div>
    </div>
    <div class="info-cell span2">
      <div class="lbl">🌗 Paksha</div>
      <div class="val small">${pak}</div>
    </div>
  `;
  document.getElementById('timingToolsCard').style.display = 'block';

  renderSlots(document.getElementById('daySlots'), payload.sunrise.hours, daySlotMin, dow, nowH, false);
  renderSlots(document.getElementById('nightSlots'), payload.sunset.hours, nightSlotMin, dow, nowH, true);

  document.getElementById('results').style.display = 'block';
  setTimeout(() => {
    document.getElementById('results').scrollIntoView({behavior: 'smooth', block: 'start'});
  }, 80);
}
