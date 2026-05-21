// 登录表单处理
document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
        setupPasswordValidation();
    }
});

// 登录处理
async function handleLogin(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = {
        username: formData.get('username'),
        password: formData.get('password'),
        role: formData.get('role') || 'user'
    };
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    try {
        submitBtn.innerHTML = '<div class="loading"></div> 登录中...';
        submitBtn.disabled = true;
        
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const isAdmin = result.role === 'admin';
            showAlert(isAdmin ? '管理员登录成功！正在跳转...' : '登录成功！正在跳转...', 'success');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1000);
        } else {
            const selectedRole = data.role === 'admin' ? '管理员' : '用户';
            showAlert(result.message || `${selectedRole}登录失败，请检查用户名和密码`, 'danger');
        }
    } catch (error) {
        console.error('Login error:', error);
        showAlert('网络错误，请稍后重试', 'danger');
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

// 注册处理
async function handleRegister(e) {
    e.preventDefault();
    console.log('注册表单提交');

    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm_password').value;

    // 密码验证
    if (password !== confirmPassword) {
        showAlert('两次输入的密码不一致', 'danger');
        return;
    }

    if (password.length < 6) {
        showAlert('密码长度至少6位', 'danger');
        return;
    }

    const username = document.getElementById('username').value;
    if (username.length < 3) {
        showAlert('用户名至少3个字符', 'danger');
        return;
    }

    // 收集表单数据
    const roleEl = document.querySelector('input[name="role"]:checked');
    const role = roleEl ? roleEl.value : 'user';
    const adminCodeEl = document.getElementById('admin_code');
    const data = {
        username: username,
        password: password,
        nickname: document.getElementById('nickname').value || null,
        age: document.getElementById('age').value ? parseInt(document.getElementById('age').value) : null,
        gender: document.getElementById('gender').value || null,
        role: role,
        admin_code: (role === 'admin' && adminCodeEl) ? adminCodeEl.value : undefined
    };

    console.log('注册数据:', data);

    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;

    try {
        submitBtn.innerHTML = '<div class="loading"></div> 注册中...';
        submitBtn.disabled = true;

        console.log('发送注册请求到 /api/register');

        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        console.log('注册响应状态:', response.status);

        const result = await response.json();
        console.log('注册响应结果:', result);

        if (response.ok && result.success) {
            const isAdmin = result.role === 'admin';
            showAlert(isAdmin ? '管理员注册成功！正在跳转...' : '注册成功！正在跳转...', 'success');
            setTimeout(() => {
                window.location.href = isAdmin ? '/ops' : '/dashboard';
            }, 1500);
        } else {
            showAlert(result.message || '注册失败，请重试', 'danger');
        }
    } catch (error) {
        console.error('Register error:', error);
        showAlert('网络错误，请稍后重试: ' + error.message, 'danger');
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

// 密码验证设置
function setupPasswordValidation() {
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');

    if (password && confirmPassword) {
        confirmPassword.addEventListener('input', function() {
            if (password.value !== confirmPassword.value) {
                confirmPassword.setCustomValidity('密码不匹配');
            } else {
                confirmPassword.setCustomValidity('');
            }
        });
    }
}

// 显示提示信息
function showAlert(message, type) {
    // 移除现有的alert
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(alert => {
        if (!alert.classList.contains('d-none')) {
            alert.remove();
        }
    });

    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    const form = document.querySelector('form');
    if (form) {
        form.parentNode.insertBefore(alertDiv, form);
    } else {
        document.body.insertBefore(alertDiv, document.body.firstChild);
    }

    // 自动消失
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.parentNode.removeChild(alertDiv);
        }
    }, 5000);
}

// 表单验证增强
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }

            form.classList.add('was-validated');
        });
    });
});