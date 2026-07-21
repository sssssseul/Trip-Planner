const WEEKDAYS = ['일요일','월요일','화요일','수요일','목요일','금요일','토요일'];
const TRIP_ID = window.location.pathname.split('/').filter(Boolean).pop();
let editingItemId = null;
let editingChkId = null;
let editMode = false;
let state = null; // loaded from server

async function api(method, url, body){
  const res = await fetch(url, {
    method,
    headers: body ? {'Content-Type':'application/json'} : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if(!res.ok) throw new Error('요청 실패: ' + url);
  return res.json();
}

function formatWeekday(dateStr){
  const d = new Date(dateStr + 'T00:00:00');
  const weekday = WEEKDAYS[d.getDay()];
  const slashDate = dateStr.replace(/-/g, '/');
  return { weekday, slashDate };
}

async function loadTrip(){
  state = await api('GET', `/api/trips/${TRIP_ID}`);
  render();
}

function render(){
  if(!state) return;
  document.getElementById('tripTitle').value = state.title;
  document.getElementById('startDate').value = state.startDate;
  document.getElementById('endDate').value = state.endDate;
  const nights = Math.max(0, state.days.length - 1);
  document.getElementById('dayCountLabel').textContent = `${nights}박 ${state.days.length}일`;

  const editModeBtn = document.getElementById('editModeBtn');
  if(editModeBtn) editModeBtn.classList.toggle('active', editMode);

  const chkAddRow = document.getElementById('chkAddRow');
  if(chkAddRow) chkAddRow.style.display = editMode ? 'flex' : 'none';

  const chkWrap = document.getElementById('chkList');
  chkWrap.innerHTML = '';
  state.checklist.forEach(item => {
    const row = document.createElement('div');
    if(editingChkId === item.id){
      row.className = 'chk-edit';
      row.innerHTML = `
        <input type="text" id="edit-chk-${item.id}" value="${escapeAttr(item.text)}">
        <button class="cancel-chk" onclick="cancelEditChk()">취소</button>
        <button class="save-chk" onclick="saveEditChk(${item.id})">저장</button>
      `;
    }else{
      row.className = 'chk-item' + (item.done ? ' done' : '');
      row.innerHTML = `
        <input type="checkbox" ${item.done ? 'checked' : ''} onchange="toggleChk(${item.id})">
        <span>${escapeHtml(item.text)}</span>
        ${editMode ? `
        <div class="actions">
          <button class="edit-btn" onclick="startEditChk(${item.id})" aria-label="수정">&#9998;</button>
          <button class="del" onclick="delChk(${item.id})" aria-label="삭제">&times;</button>
        </div>` : ''}
      `;
    }
    chkWrap.appendChild(row);
  });

  const daysWrap = document.getElementById('daysScroll');
  daysWrap.innerHTML = '';
  state.days.forEach((day, idx) => {
    const { weekday, slashDate } = formatWeekday(day.date);
    const card = document.createElement('div');
    card.className = 'day-card';
    card.innerHTML = `
      <div class="day-head">
        <div class="day-label">DAY ${idx + 1}</div>
        <div class="weekday-row">
          <div class="weekday">${weekday}</div>
          <div class="date">(${slashDate})</div>
        </div>
      </div>
      <div class="main-event">
        <span class="event-flag">&#10003;</span>
        <input type="text" placeholder="오늘의 메인 이벤트" value="${escapeAttr(day.mainEvent || '')}"
               onchange="updateMainEvent('${day.date}', this.value)">
      </div>
      <div class="day-body">
        <div class="items">
          ${day.items.map(it => renderItem(day.date, it)).join('')}
        </div>
        <div class="item-add" style="display:${editMode ? 'flex' : 'none'}">
          <div class="item-add-row">
            <input type="time" id="time-start-${day.date}">
            <span class="time-sep">~</span>
            <input type="time" id="time-end-${day.date}">
          </div>
          <input type="text" id="text-${day.date}" placeholder="일정">
          <input type="text" id="note-${day.date}" placeholder="메모">
          <label class="toggle-transport">
            <input type="checkbox" id="transport-${day.date}"> 이동/교통
          </label>
          <button class="item-add-btn" onclick="addItem('${day.date}')">+ 추가</button>
        </div>
      </div>
    `;
    daysWrap.appendChild(card);
  });
}

function renderItem(date, it){
  if(editingItemId === it.id){
    return `
      <div class="item-edit">
        <div class="item-edit-row">
          <input type="time" id="edit-time-${it.id}" value="${escapeAttr(it.time || '')}">
          <span class="time-sep">~</span>
          <input type="time" id="edit-time-end-${it.id}" value="${escapeAttr(it.endTime || '')}">
        </div>
        <input type="text" id="edit-text-${it.id}" value="${escapeAttr(it.text)}" placeholder="일정">
        <input type="text" id="edit-note-${it.id}" value="${escapeAttr(it.note || '')}" placeholder="메모">
        <div class="edit-controls">
          <label class="toggle-transport">
            <input type="checkbox" id="edit-transport-${it.id}" ${it.transport ? 'checked' : ''}> 이동/교통
          </label>
          <div class="edit-buttons">
            <button class="cancel-item" onclick="cancelEditItem()">취소</button>
            <button class="save-item" onclick="saveEditItem(${it.id})">저장</button>
          </div>
        </div>
      </div>
    `;
  }
  const timeLabel = it.endTime ? `${it.time || ''} - ${it.endTime}` : (it.time || '');
  return `
    <div class="item ${it.transport ? 'transport' : ''}">
      <div class="item-top">
        <div class="item-main">
          <span class="time">${escapeHtml(timeLabel)}</span>
          <span class="text">${escapeHtml(it.text)}</span>
        </div>
        ${editMode ? `
        <div class="actions">
          <button onclick="startEditItem(${it.id})" aria-label="수정">&#9998;</button>
          <button class="del-btn" onclick="delItem(${it.id})" aria-label="삭제">&times;</button>
        </div>` : ''}
      </div>
      ${it.note ? `<span class="note">${escapeHtml(it.note)}</span>` : ''}
    </div>
  `;
}

function escapeHtml(s){
  const d = document.createElement('div');
  d.textContent = s == null ? '' : s;
  return d.innerHTML;
}
function escapeAttr(s){
  return escapeHtml(s).replace(/"/g, '&quot;');
}

// ---------- trip meta ----------

document.getElementById('tripTitle').addEventListener('change', async e => {
  state.title = e.target.value;
  try{ await api('PUT', `/api/trips/${TRIP_ID}`, {title: state.title}); }catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
});

document.getElementById('startDate').addEventListener('change', async e => {
  const startDate = e.target.value;
  try{
    await api('PUT', `/api/trips/${TRIP_ID}`, {startDate, endDate: state.endDate < startDate ? startDate : state.endDate});
    await loadTrip();
  }catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
});

document.getElementById('endDate').addEventListener('change', async e => {
  const endDate = e.target.value;
  try{
    await api('PUT', `/api/trips/${TRIP_ID}`, {endDate, startDate: state.startDate > endDate ? endDate : state.startDate});
    await loadTrip();
  }catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
});

// ---------- checklist ----------

document.getElementById('chkInput').addEventListener('keydown', e => { if(e.key === 'Enter') addChecklist(); });

async function addChecklist(){
  const input = document.getElementById('chkInput');
  const val = input.value.trim();
  if(!val) return;
  try{
    const item = await api('POST', `/api/trips/${TRIP_ID}/checklist`, {text: val});
    state.checklist.push(item);
    input.value = '';
    render();
  }catch(err){ showToast('추가 실패. 다시 시도해주세요.'); }
}

async function toggleChk(id){
  const item = state.checklist.find(c => c.id === id);
  if(!item) return;
  item.done = !item.done;
  render();
  try{ await api('PATCH', `/api/checklist/${id}`, {done: item.done}); }
  catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
}

async function delChk(id){
  state.checklist = state.checklist.filter(c => c.id !== id);
  if(editingChkId === id) editingChkId = null;
  render();
  try{ await api('DELETE', `/api/checklist/${id}`); }
  catch(err){ showToast('삭제 실패. 다시 시도해주세요.'); }
}

function startEditChk(id){
  editingChkId = id;
  render();
}
function cancelEditChk(){
  editingChkId = null;
  render();
}
async function saveEditChk(id){
  const text = document.getElementById('edit-chk-' + id).value.trim();
  if(!text) return;
  const item = state.checklist.find(c => c.id === id);
  if(item) item.text = text;
  editingChkId = null;
  render();
  try{ await api('PATCH', `/api/checklist/${id}`, {text}); }
  catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
}
function toggleEditMode(){
  editMode = !editMode;
  render();
}

// ---------- day main event ----------

async function updateMainEvent(date, val){
  const day = state.days.find(d => d.date === date);
  if(day) day.mainEvent = val;
  try{ await api('PUT', `/api/trips/${TRIP_ID}/day`, {date, mainEvent: val}); }
  catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
}

// ---------- itinerary items ----------

async function addItem(date){
  const timeStartInput = document.getElementById('time-start-' + date);
  const timeEndInput = document.getElementById('time-end-' + date);
  const textInput = document.getElementById('text-' + date);
  const noteInput = document.getElementById('note-' + date);
  const transportInput = document.getElementById('transport-' + date);
  const text = textInput.value.trim();
  if(!text) return;
  try{
    const item = await api('POST', `/api/trips/${TRIP_ID}/items`, {
      date, time: timeStartInput.value, endTime: timeEndInput.value,
      text, note: noteInput.value.trim(), transport: transportInput.checked
    });
    const day = state.days.find(d => d.date === date);
    day.items.push(item);
    noteInput.value = '';
    render();
  }catch(err){ showToast('추가 실패. 다시 시도해주세요.'); }
}

function startEditItem(itemId){
  editingItemId = itemId;
  render();
}
function cancelEditItem(){
  editingItemId = null;
  render();
}

async function saveEditItem(itemId){
  const time = document.getElementById('edit-time-' + itemId).value;
  const endTime = document.getElementById('edit-time-end-' + itemId).value;
  const text = document.getElementById('edit-text-' + itemId).value.trim();
  const note = document.getElementById('edit-note-' + itemId).value.trim();
  const transport = document.getElementById('edit-transport-' + itemId).checked;
  if(!text) return;
  for(const day of state.days){
    const item = day.items.find(it => it.id === itemId);
    if(item){ item.time = time; item.endTime = endTime; item.text = text; item.note = note; item.transport = transport; break; }
  }
  editingItemId = null;
  render();
  try{ await api('PATCH', `/api/items/${itemId}`, {time, endTime, text, note, transport}); }
  catch(err){ showToast('저장 실패. 다시 시도해주세요.'); }
}

async function delItem(itemId){
  state.days.forEach(day => { day.items = day.items.filter(it => it.id !== itemId); });
  if(editingItemId === itemId) editingItemId = null;
  render();
  try{ await api('DELETE', `/api/items/${itemId}`); }
  catch(err){ showToast('삭제 실패. 다시 시도해주세요.'); }
}

// ---------- save button ----------
// 모든 변경사항은 입력 즉시 DB에 저장돼요. 이 버튼은 저장 중인 입력칸의
// 포커스를 해제해서 마지막 입력까지 확실히 반영시키고 확인 메시지를 보여줘요.

function saveAll(){
  if(document.activeElement) document.activeElement.blur();
  showToast('모두 저장됐어요.');
}

let toastTimer = null;
function showToast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
}

loadTrip().catch(() => showToast('불러오기 실패. 새로고침해보세요.'));
