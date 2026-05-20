/* ── Panel switching ── */
function showLogin() {
  document.getElementById('registerPanel').classList.remove('active');
  document.getElementById('loginPanel').classList.add('active');
  // Clear login alerts when switching
  document.getElementById('loginErrorAlert').classList.remove('show');
}

function showRegister() {
  document.getElementById('loginPanel').classList.remove('active');
  document.getElementById('registerPanel').classList.add('active');
  // Clear reg alerts when switching back
  document.getElementById('regErrorAlert').classList.remove('show');
}

/* ── Password toggle ── */
function togglePw(id, btn) {
  const input = document.getElementById(id);
  const show  = input.type === 'password';
  input.type  = show ? 'text' : 'password';
  btn.querySelector('.eye-icon').style.display     = show ? 'none' : '';
  btn.querySelector('.eye-off-icon').style.display  = show ? ''     : 'none';
}

/* ── Registration ── */
async function handleRegister() {
  const name  = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const pw    = document.getElementById('reg-pw').value;
  const cpw   = document.getElementById('reg-cpw').value;
  // const terms = document.getElementById('termsCheck').checked;

  document.getElementById('regSuccessAlert').classList.remove('show');
  document.getElementById('regErrorAlert').classList.remove('show');

  if (!name || !email || !pw || !cpw) { showRegError('Please fill in all fields.'); return; }
  if (pw !== cpw)                      { showRegError('Passwords do not match.'); return; }
  // if (!terms)                          { showRegError('Please accept the terms & conditions.'); return; }

  setRegLoading(true);

  try {
    const res  = await fetch('/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password: pw, confirm: cpw })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      // Hide form, show success with "Go to Login" button
      document.getElementById('registerForm').style.display = 'none';
      document.getElementById('regSuccessAlert').classList.add('show');
    } else {
      showRegError(data.message || 'Registration failed. Please try again.');
      setRegLoading(false);
    }
  } catch (err) {
    showRegError('Network error. Please check your connection.');
    setRegLoading(false);
  }
}

function showRegError(msg) {
  document.getElementById('regErrorMsg').textContent = msg;
  document.getElementById('regErrorAlert').classList.add('show');
}

function setRegLoading(on) {
  const btn = document.getElementById('registerBtn');
  btn.disabled = on;
  document.getElementById('regSpinner').style.display = on ? 'block' : 'none';
  document.getElementById('regBtnText').textContent   = on ? 'Registering...' : 'Register Now';
}

/* ── Login ── */
async function handleLogin() {
  const email    = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-pw').value;

  document.getElementById('loginErrorAlert').classList.remove('show');

  if (!email || !password) { showLoginError('Please fill in all fields.'); return; }

  setLoginLoading(true);

  try {
    const res  = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      window.location.href = data.redirect || '/dashboard';
    } else {
      showLoginError(data.message || 'Login failed. Please try again.');
      setLoginLoading(false);
    }
  } catch (err) {
    showLoginError('Network error. Please check your connection.');
    setLoginLoading(false);
  }
}

function showLoginError(msg) {
  document.getElementById('loginErrorMsg').textContent = msg;
  document.getElementById('loginErrorAlert').classList.add('show');
}

function setLoginLoading(on) {
  const btn = document.getElementById('loginBtn');
  btn.disabled = on;
  document.getElementById('loginSpinner').style.display = on ? 'block' : 'none';
  document.getElementById('loginBtnText').textContent   = on ? 'Logging in...' : 'Login Now';
}