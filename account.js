async function api(method, url, body){
  const res = await fetch(url, {
    method,
    headers: body ? {'Content-Type':'application/json'} : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if(res.status === 401){
    window.location.href = '/login';
    throw new Error('로그인이 필요해요.');
  }
  const data = await res.json().catch(() => ({}));
  if(!res.ok) throw new Error(data.error || '요청 실패');
  return data;
}

function showMsg(el, text, type){
  el.textContent = text;
  el.className = 'msg ' + type;
}

document.getElementById('usernameForm').addEventListener('submit', async e => {
  e.preventDefault();
  const newUsername = document.getElementById('newUsername').value.trim();
  const password = document.getElementById('usernamePassword').value;
  const msg = document.getElementById('usernameMsg');
  try{
    await api('PUT', '/api/account/username', {newUsername, password});
    showMsg(msg, '아이디가 변경됐어요.', 'success');
    document.getElementById('usernamePassword').value = '';
  }catch(err){
    showMsg(msg, err.message || '변경 실패', 'error');
  }
});

document.getElementById('passwordForm').addEventListener('submit', async e => {
  e.preventDefault();
  const currentPassword = document.getElementById('currentPassword').value;
  const newPassword = document.getElementById('newPassword').value;
  const newPasswordConfirm = document.getElementById('newPasswordConfirm').value;
  const msg = document.getElementById('passwordMsg');

  if(newPassword !== newPasswordConfirm){
    showMsg(msg, '새 비밀번호가 서로 달라요.', 'error');
    return;
  }

  try{
    await api('PUT', '/api/account/password', {currentPassword, newPassword});
    showMsg(msg, '비밀번호가 변경됐어요.', 'success');
    document.getElementById('passwordForm').reset();
  }catch(err){
    showMsg(msg, err.message || '변경 실패', 'error');
  }
});
