async function api(method, url, body){
  const res = await fetch(url, {
    method,
    headers: body ? {'Content-Type':'application/json'} : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  if(!res.ok) throw new Error(data.error || '요청 실패');
  return data;
}

let mode = window.location.pathname === '/signup' ? 'signup' : 'login';

const formTitle = document.getElementById('formTitle');
const submitBtn = document.getElementById('submitBtn');
const switchRow = document.getElementById('switchRow');
const switchLink = document.getElementById('switchLink');
const confirmField = document.getElementById('confirmField');
const confirmInput = document.getElementById('confirmPassword');
const errorMsg = document.getElementById('errorMsg');
const form = document.getElementById('authForm');

function applyMode(){
  if(mode === 'signup'){
    formTitle.textContent = '회원가입';
    submitBtn.textContent = '가입하기';
    confirmField.style.display = 'block';
    confirmInput.required = true;
    switchRow.innerHTML = '이미 계정이 있으신가요? <a id="switchLink">로그인</a>';
    history.replaceState(null, '', '/signup');
  }else{
    formTitle.textContent = '로그인';
    submitBtn.textContent = '로그인';
    confirmField.style.display = 'none';
    confirmInput.required = false;
    switchRow.innerHTML = '계정이 없으신가요? <a id="switchLink">회원가입</a>';
    history.replaceState(null, '', '/login');
  }
  document.getElementById('switchLink').addEventListener('click', () => {
    mode = mode === 'signup' ? 'login' : 'signup';
    hideError();
    applyMode();
  });
}

function showError(msg){
  errorMsg.textContent = msg;
  errorMsg.classList.add('show');
}
function hideError(){
  errorMsg.classList.remove('show');
}

form.addEventListener('submit', async e => {
  e.preventDefault();
  hideError();

  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  if(mode === 'signup'){
    const confirm = confirmInput.value;
    if(password !== confirm){
      showError('비밀번호가 서로 달라요.');
      return;
    }
  }

  submitBtn.disabled = true;
  try{
    if(mode === 'signup'){
      await api('POST', '/api/signup', {username, password});
    }else{
      await api('POST', '/api/login', {username, password});
    }
    window.location.href = '/trips';
  }catch(err){
    showError(err.message || '다시 시도해주세요.');
  }finally{
    submitBtn.disabled = false;
  }
});

applyMode();
