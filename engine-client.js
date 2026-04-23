function escapeSlotHtml(text){
  return String(text).replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}

function formatSlotBhargavResult(result){
  if(typeof formatBhargavResult === 'function'){
    return formatBhargavResult(result);
  }
  return escapeSlotHtml(result);
}

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
let latestBalamPayload = null;

const PANCHANGA_LABEL_I18N = {
  te: {
    "Date & Weekday": "తేదీ & వారం",
    "Place": "ప్రదేశం",
    "Vara": "వారం",
    "Hora": "హోరా",
    "Lagna": "లగ్నం",
    "Sunrise": "సూర్యోదయం",
    "Sunset": "సూర్యాస్తమయం",
    "Day Length": "పగటి నిడివి",
    "Night Length": "రాత్రి నిడివి",
    "Hindu Month": "హిందూ మాసం",
    "Surya Rasi": "సూర్య రాశి",
    "Tithi": "తిథి",
    "Nakshatra": "నక్షత్రం",
    "Yoga": "యోగం",
    "Karana": "కరణం",
    "Rahu Kalam": "రాహుకాలం",
    "Yamagandam": "యమగండం",
    "Durmuhurtam": "దుర్ముహూర్తం",
    "Amrita Gadiyalu": "అమృత ఘడియలు",
    "Varjyam": "వర్జ్యం",
    "Paksha": "పక్షం",
    "Gulika": "గుళిక"
  },
  hi: {
    "Date & Weekday": "तिथि और वार",
    "Place": "स्थान",
    "Vara": "वार",
    "Hora": "होरा",
    "Lagna": "लग्न",
    "Sunrise": "सूर्योदय",
    "Sunset": "सूर्यास्त",
    "Day Length": "दिन की अवधि",
    "Night Length": "रात्रि अवधि",
    "Hindu Month": "हिंदू मास",
    "Surya Rasi": "सूर्य राशि",
    "Tithi": "तिथि",
    "Nakshatra": "नक्षत्र",
    "Yoga": "योग",
    "Karana": "करण",
    "Rahu Kalam": "राहुकाल",
    "Yamagandam": "यमगण्ड",
    "Durmuhurtam": "दुर्मुहूर्त",
    "Amrita Gadiyalu": "अमृत काल",
    "Varjyam": "वर्ज्य",
    "Paksha": "पक्ष",
    "Gulika": "गुलिक"
  },
  ta: {
    "Date & Weekday": "தேதி & கிழமை",
    "Place": "இடம்",
    "Vara": "வாரம்",
    "Hora": "ஹோரை",
    "Lagna": "லக்னம்",
    "Sunrise": "சூரிய உதயம்",
    "Sunset": "சூரிய அஸ்தமனம்",
    "Day Length": "பகல் நீளம்",
    "Night Length": "இரவு நீளம்",
    "Hindu Month": "இந்து மாதம்",
    "Surya Rasi": "சூரிய ராசி",
    "Tithi": "திதி",
    "Nakshatra": "நட்சத்திரம்",
    "Yoga": "யோகம்",
    "Karana": "கரணம்",
    "Rahu Kalam": "ராகு காலம்",
    "Yamagandam": "எமகண்டம்",
    "Durmuhurtam": "துர்முஹூர்த்தம்",
    "Amrita Gadiyalu": "அமிர்த காலம்",
    "Varjyam": "வர்ஜ்யம்",
    "Paksha": "பக்ஷம்",
    "Gulika": "குளிகை"
  },
  kn: {
    "Date & Weekday": "ದಿನಾಂಕ & ವಾರ",
    "Place": "ಸ್ಥಳ",
    "Vara": "ವಾರ",
    "Hora": "ಹೋರಾ",
    "Lagna": "ಲಗ್ನ",
    "Sunrise": "ಸೂರ್ಯೋದಯ",
    "Sunset": "ಸೂರ್ಯಾಸ್ತ",
    "Day Length": "ಹಗಲಿನ ಅವಧಿ",
    "Night Length": "ರಾತ್ರಿಯ ಅವಧಿ",
    "Hindu Month": "ಹಿಂದೂ ಮಾಸ",
    "Surya Rasi": "ಸೂರ್ಯ ರಾಶಿ",
    "Tithi": "ತಿಥಿ",
    "Nakshatra": "ನಕ್ಷತ್ರ",
    "Yoga": "ಯೋಗ",
    "Karana": "ಕರಣ",
    "Rahu Kalam": "ರಾಹುಕಾಲ",
    "Yamagandam": "ಯಮಗಂಡ",
    "Durmuhurtam": "ದುರ್ಮುಹೂರ್ತ",
    "Amrita Gadiyalu": "ಅಮೃತ ಕಾಲ",
    "Varjyam": "ವರ್ಜ್ಯ",
    "Paksha": "ಪಕ್ಷ",
    "Gulika": "ಗುಳಿಕ"
  }
};

function panchangaLabel(label){
  const lang = typeof getDisplayLang === 'function' ? getDisplayLang() : 'en';
  const translated = PANCHANGA_LABEL_I18N[lang]?.[label];
  const english = label === 'Rahu Kalam' ? 'Rahukala' : label === 'Amrita Gadiyalu' ? 'Amrita Kalam' : label;
  if(!translated || lang === 'en') return escapeSlotHtml(english);
  return `${escapeSlotHtml(translated)} / ${escapeSlotHtml(english)}`;
}

function rangesOverlap(startA, endA, startB, endB){
  return startA < endB && endA > startB;
}

function collectSlotMarkers(t0, t1, panchangaFlags){
  if(!panchangaFlags) return {};
  const inRange = item => item && rangesOverlap(t0, t1, item.start_hours, item.end_hours);
  return {
    rahu: inRange(panchangaFlags.rahu),
    yama: inRange(panchangaFlags.yama),
    amrita: (panchangaFlags.amrita || []).some(inRange),
    dur: (panchangaFlags.dur || []).some(inRange),
    gulika: inRange(panchangaFlags.gulika),
  };
}

function slotFlag(label, active, className=''){
  return `<div class="slot-flag ${active ? `active ${className}` : ''}">${active ? label : '-'}</div>`;
}

function renderSlots(container, startH, slotMinutes, dow, nowH, isNight, panchangaFlags=null){
  let html='';
  for(let i=0;i<30;i++){
    const t0=startH+i*slotMinutes/60;
    const t1=t0+slotMinutes/60;
    const result=BHARGAV[i][dow];
    const cat=getCategory(result);
    const isNow=nowH>=t0&&nowH<t1;
    const markers = collectSlotMarkers(t0, t1, panchangaFlags);
    html+=`<div class="slot${isNow?' now':''}${isNight?' night-slot':''}">
      <div class="time">${hToTime(t0)}<br><small style="font-size:0.65rem;opacity:0.7;">to ${hToTime(t1)}</small></div>
      <div class="result ${cat}">${formatSlotBhargavResult(result)}${isNow?'<span class="now-badge">NOW</span>':''}</div>
      ${slotFlag('☊', markers.rahu, 'bad')}
      ${slotFlag('YG', markers.yama, 'bad')}
      ${slotFlag('AG', markers.amrita, 'good')}
      ${slotFlag('DM', markers.dur, 'bad')}
      ${slotFlag('GK', markers.gulika, 'bad')}
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

function renderChandrabalaTable(){
  const segments = latestBalamPayload?.chandrabala_segments || [];
  if(segments.length){
    return `${segments.map(segment => `
      <div class="timeline-row" style="display:block;">
        <div class="timeline-time">${escapeSlotHtml(segment.display)}</div>
        <div class="timeline-name">Moon in ${escapeSlotHtml(segment.transit_moon_rasi.name)}</div>
        <div style="font-size:0.72rem;color:#F7F0D6;margin-top:5px;">Good: ${segment.good_rasis.map(item => escapeSlotHtml(item.name)).join(', ')}</div>
        <div style="font-size:0.7rem;color:#FFB06E;margin-top:5px;">Ashtama Chandra: ${escapeSlotHtml(segment.ashtama_chandra.rasi_name)} (${escapeSlotHtml(segment.ashtama_chandra.padas)})</div>
      </div>
      <table class="balam-table" style="margin-top:8px;">
        <thead><tr><th>Birth Rasi</th><th>Status</th><th>Birth Nakshatra Padas</th></tr></thead>
        <tbody>${segment.rows.map(row => {
          const statusClass = row.status === 'Good' ? 'balam-status-good' : row.status === 'Puja Needed' ? '' : 'balam-status-bad';
          return `<tr>
            <td>${escapeSlotHtml(row.rasi_name)}</td>
            <td class="${statusClass}">${escapeSlotHtml(row.status)}</td>
            <td>${escapeSlotHtml(row.padas)}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    `).join('')}
    <button class="timeline-btn" type="button" style="margin-top:10px;width:100%;" onclick="openChandrabalaPopup()">Open Chandrabala Popup</button>`;
  }
  const rows = latestBalamPayload?.chandrabala || [];
  if(!rows.length) return '<div class="timeline-empty">No Chandrabala values available.</div>';
  return `<table class="balam-table">
    <thead><tr><th>Good Birth Rasis</th></tr></thead>
    <tbody><tr><td>${rows.map(item => escapeSlotHtml(item.name)).join(', ')}</td></tr></tbody>
  </table>`;
}

function openChandrabalaPopup(){
  const segments = latestBalamPayload?.chandrabala_segments || [];
  if(!segments.length) return;
  const body = document.getElementById('timelineModalBody');
  const title = document.getElementById('timelineModalTitle');
  title.textContent = 'Chandrabala Pada Details';
  body.innerHTML = segments.map(segment => `
    <div class="timeline-note">For ${escapeSlotHtml(segment.display)}: transit Moon in ${escapeSlotHtml(segment.transit_moon_rasi.name)}</div>
    <table class="balam-table">
      <thead><tr><th>Birth Rasi</th><th>Status</th><th>Birth Nakshatra Padas</th></tr></thead>
      <tbody>${segment.rows.map(row => {
        const statusClass = row.status === 'Good' ? 'balam-status-good' : row.status === 'Puja Needed' ? '' : 'balam-status-bad';
        return `<tr>
          <td>${escapeSlotHtml(row.rasi_name)}</td>
          <td class="${statusClass}">${escapeSlotHtml(row.status)}</td>
          <td>${escapeSlotHtml(row.padas)}</td>
        </tr>`;
      }).join('')}</tbody>
    </table>
  `).join('');
  document.getElementById('timelineModal').style.display = 'flex';
}

function renderTarabalaTable(){
  const rows = latestBalamPayload?.tarabala || [];
  if(!rows.length) return '<div class="timeline-empty">No Tarabala values available.</div>';
  return `<table class="balam-table">
    <thead><tr><th>Tarabala</th><th>Result</th><th>Birth Stars</th></tr></thead>
    <tbody>${rows.map(row => {
      const good = !/bad|not good/i.test(row.result);
      return `<tr>
        <td>${escapeSlotHtml(row.name)}</td>
        <td class="${good ? 'balam-status-good' : 'balam-status-bad'}">${escapeSlotHtml(row.result)}</td>
        <td>${(row.stars || []).map(star => escapeSlotHtml(star.name)).join(', ')}</td>
      </tr>`;
    }).join('')}</tbody>
  </table>`;
}

function showBalamTab(kind){
  document.getElementById('chandraBalaTab')?.classList.toggle('active', kind === 'chandra');
  document.getElementById('taraBalaTab')?.classList.toggle('active', kind === 'tara');
  const body = document.getElementById('balamBody');
  if(!body) return;
  body.innerHTML = kind === 'tara' ? renderTarabalaTable() : renderChandrabalaTable();
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
  const amritaHtml = withValidationNote(formatEngineEventList(payload.amrita_gadiyalu));
  const varjyamHtml = withValidationNote(formatEngineEventList(payload.varjyam));
  latestTimelinePayload = payload;
  latestBalamPayload = payload.balam || null;
  const slotFlags = {
    rahu: payload.rahu_kalam,
    yama: payload.yamagandam,
    amrita: payload.amrita_gadiyalu || [],
    dur: payload.durmuhurtam || [],
    gulika: payload.gulika,
  };

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
      <div class="lbl">${panchangaLabel('Vara')}</div>
      <div class="val small">${payload.weekday.name}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Hora')}</div>
      <div class="val small">${payload.hora.ruler}<br><span style="font-size:0.68rem;color:#FFCC88;">${payload.hora.display}</span></div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Lagna')}</div>
      <div class="val small">${payload.lagna?.display || '--'}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🌄 ${panchangaLabel('Sunrise')}</div>
      <div class="val green">${payload.sunrise.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🌇 ${panchangaLabel('Sunset')}</div>
      <div class="val orange">${payload.sunset.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🕐 ${panchangaLabel('Day Length')}</div>
      <div class="val small">${payload.day_length.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">🌙 ${panchangaLabel('Night Length')}</div>
      <div class="val small">${payload.night_length.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">📆 ${panchangaLabel('Hindu Month')}</div>
      <div class="val small">${payload.masa.name}${payload.masa.adhika ? ' (Adhika)' : ''}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">☀️ ${panchangaLabel('Surya Rasi')}</div>
      <div class="val small">${payload.rasi.name}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${moonEmoji(payload.tithi.number - 1)} ${panchangaLabel('Tithi')}</div>
      <div class="val small">${formatSameDayEntries(payload.tithi.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">తిథి (Telugu)</div>
      <div class="val small">${teluguTithi}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Nakshatra')}</div>
      <div class="val small">${formatSameDayEntries(payload.nakshatra.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Yoga')}</div>
      <div class="val small">${formatSameDayEntries(payload.yoga.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Karana')}</div>
      <div class="val small">${formatSameDayEntries(payload.karana.entries)}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Rahu Kalam')}</div>
      <div class="val small">${payload.rahu_kalam.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Yamagandam')}</div>
      <div class="val small">${payload.yamagandam.display}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Durmuhurtam')}</div>
      <div class="val small">${durmuhurtaHtml}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Amrita Gadiyalu')}</div>
      <div class="val small">${amritaHtml}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Gulika')}</div>
      <div class="val small">${payload.gulika?.display || '--'}</div>
    </div>
    <div class="info-cell">
      <div class="lbl">${panchangaLabel('Varjyam')}</div>
      <div class="val small">${varjyamHtml}</div>
    </div>
    <div class="info-cell span2">
      <div class="lbl">🌗 ${panchangaLabel('Paksha')}</div>
      <div class="val small">${pak}</div>
    </div>
  `;
  document.getElementById('timingToolsCard').style.display = 'block';
  document.getElementById('balamCard').style.display = latestBalamPayload ? 'block' : 'none';
  showBalamTab('chandra');

  renderSlots(document.getElementById('daySlots'), payload.sunrise.hours, daySlotMin, dow, nowH, false, slotFlags);
  renderSlots(document.getElementById('nightSlots'), payload.sunset.hours, nightSlotMin, dow, nowH, true, slotFlags);

  document.getElementById('results').style.display = 'block';
  setTimeout(() => {
    document.getElementById('results').scrollIntoView({behavior: 'smooth', block: 'start'});
  }, 80);
}
