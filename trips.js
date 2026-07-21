async function api(method, url, body){
  const res = await fetch(url, {
    method,
    headers: body ? {'Content-Type':'application/json'} : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if(!res.ok) throw new Error('요청 실패: ' + url);
  return res.json();
}

function escapeHtml(s){
  const d = document.createElement('div');
  d.textContent = s == null ? '' : s;
  return d.innerHTML;
}

function formatRange(startDate, endDate){
  return `${startDate.replace(/-/g,'/')} → ${endDate.replace(/-/g,'/')}`;
}

async function loadTrips(){
  const grid = document.getElementById('tripGrid');
  let trips = [];
  try{
    trips = await api('GET', '/api/trips');
  }catch(err){
    grid.innerHTML = '<p class="empty-note">여행 목록을 불러오지 못했어요. 새로고침해보세요.</p>';
    return;
  }

  grid.innerHTML = '';

  trips.forEach(trip => {
    const card = document.createElement('button');
    card.className = 'trip-card';
    card.onclick = () => { window.location.href = `/trip/${trip.id}`; };
    card.innerHTML = `
      <button class="del" aria-label="삭제">&times;</button>
      <div class="band">
        <div class="label">TRIP</div>
        <h3>${escapeHtml(trip.title)}</h3>
      </div>
      <div class="body">
        <div class="dates">${formatRange(trip.startDate, trip.endDate)}</div>
        <div class="stats">
          <span>✓ 체크리스트 ${trip.checklistCount}</span>
          <span>◆ 일정 ${trip.itemCount}</span>
        </div>
      </div>
    `;
    const delBtn = card.querySelector('.del');
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if(!confirm(`"${trip.title}" 여행을 삭제할까요? 되돌릴 수 없어요.`)) return;
      try{
        await api('DELETE', `/api/trips/${trip.id}`);
        loadTrips();
      }catch(err){
        alert('삭제에 실패했어요. 다시 시도해주세요.');
      }
    });
    grid.appendChild(card);
  });

  const newCard = document.createElement('button');
  newCard.className = 'new-trip-card';
  newCard.innerHTML = `<div class="plus">+</div><span class="label-text">새 여행 만들기</span>`;
  newCard.onclick = async () => {
    const title = prompt('여행 이름을 입력해주세요', '새 여행');
    if(title === null) return;
    try{
      const result = await api('POST', '/api/trips', {title});
      window.location.href = `/trip/${result.id}`;
    }catch(err){
      alert('여행 만들기에 실패했어요. 다시 시도해주세요.');
    }
  };
  grid.appendChild(newCard);

  if(trips.length === 0){
    const note = document.createElement('p');
    note.className = 'empty-note';
    note.style.gridColumn = '1 / -1';
    note.textContent = '아직 만든 여행이 없어요. "+ 새 여행 만들기"로 시작해보세요.';
    grid.insertBefore(note, newCard);
  }
}

loadTrips();
