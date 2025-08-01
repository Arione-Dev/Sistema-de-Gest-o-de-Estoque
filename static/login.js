


console.log('Carregando login.js...');

async function login() {
    const matricula = document.getElementById('matriculaInput').value.trim();
    const senha = document.getElementById('senhaInput').value.trim();
    const deviceType = document.getElementById('deviceType').value;

    console.log(`Tentativa de login - Matrícula: ${matricula}, Dispositivo: ${deviceType}`);

    if (!matricula || !senha) {
        alert('Por favor, preencha todos os campos.');
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ matricula, senha, deviceType }),
        });

        const data = await response.json();

        if (data.success) {
            console.log('Login bem-sucedido, redirecionando para:', data.redirect);
            window.location.href = data.redirect || '/default';
        } else {
            console.error('Erro no login:', data.message);
            alert(data.message || 'Erro ao fazer login. Verifique suas credenciais.');
        }
    } catch (error) {
        console.error('Erro na requisição:', error);
        alert('Erro ao conectar com o servidor. Tente novamente.');
    }
}

document.addEventListener('keypress', (event) => {
    console.log('Tecla pressionada (keypress global):', event.key, 'Código:', event.keyCode);
    if (event.keyCode === 13 || event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        console.log('Enter detectado. Executando login().');
        login();
    }
});

document.addEventListener('keydown', (event) => {
    console.log('Evento keydown global detectado. Tecla:', event.key, 'Código:', event.keyCode);
    if (event.keyCode === 13 || event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        console.log('Enter bloqueado globalmente via keydown.');
    }
});

document.addEventListener('submit', (event) => {
    event.preventDefault();
    event.stopPropagation();
    console.log('Submissão de formulário bloqueada globalmente.');
});


console.log('login.js carregado com sucesso.');