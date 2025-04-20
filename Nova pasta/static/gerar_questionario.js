let currentCandidatoId = null;
let currentQuestionario = [];

// Função para exibir o popup do formulário
function showFormularioPopup(candidatoId, tituloVaga, requisitos) {
    currentCandidatoId = candidatoId;
    const popup = document.getElementById('formularioPopup');
    const formularioContent = document.getElementById('formularioContent');
    const candidateNameSpan = document.getElementById('formularioCandidateName');

    // Buscar o nome do candidato na tabela
    const candidateRow = document.querySelector(`tr[data-candidato-id="${candidatoId}"]`);
    const candidateName = candidateRow.querySelector('.candidate-name').textContent;
    candidateNameSpan.textContent = candidateName;

    // Fazer uma requisição para obter as perguntas geradas pela IA
    fetch(`/gerar_perguntas/${candidatoId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => { throw new Error(`Erro ao obter perguntas: ${text}`); });
        }
        return response.json();
    })
    .then(data => {
        currentQuestionario = data.perguntas;

        // Renderizar as questões no popup
        formularioContent.innerHTML = '';
        currentQuestionario.forEach((questao, index) => {
            const questaoDiv = document.createElement('div');
            questaoDiv.className = 'questao';
            questaoDiv.innerHTML = `
                <label>Pergunta ${index + 1}</label>
                <input type="text" class="pergunta-input" value="${questao.pergunta}" data-index="${index}">
                <div class="alternativa">
                    <input type="radio" name="correta-${index}" value="a" ${questao.correta === 'a' ? 'checked' : ''}>
                    <label>a)</label>
                    <input type="text" class="alternativa-input" value="${questao.alternativas[0]}" data-index="${index}" data-alt="a">
                </div>
                <div class="alternativa">
                    <input type="radio" name="correta-${index}" value="b" ${questao.correta === 'b' ? 'checked' : ''}>
                    <label>b)</label>
                    <input type="text" class="alternativa-input" value="${questao.alternativas[1]}" data-index="${index}" data-alt="b">
                </div>
                <div class="alternativa">
                    <input type="radio" name="correta-${index}" value="c" ${questao.correta === 'c' ? 'checked' : ''}>
                    <label>c)</label>
                    <input type="text" class="alternativa-input" value="${questao.alternativas[2]}" data-index="${index}" data-alt="c">
                </div>
                <div class="alternativa">
                    <input type="radio" name="correta-${index}" value="d" ${questao.correta === 'd' ? 'checked' : ''}>
                    <label>d)</label>
                    <input type="text" class="alternativa-input" value="${questao.alternativas[3]}" data-index="${index}" data-alt="d">
                </div>
            `;
            formularioContent.appendChild(questaoDiv);
        });

        popup.style.display = 'flex';
    })
    .catch(err => {
        console.error('Erro:', err);
        alert(`Erro ao obter perguntas: ${err.message}`);
    });
}

// Função para fechar o popup do formulário
function closeFormularioPopup() {
    const popup = document.getElementById('formularioPopup');
    popup.style.display = 'none';
    currentCandidatoId = null;
    currentQuestionario = [];
}

// Função para salvar o questionário
function salvarQuestionario() {
    // Atualizar o questionário com os valores editados
    const perguntasInputs = document.querySelectorAll('.pergunta-input');
    const alternativasInputs = document.querySelectorAll('.alternativa-input');
    const corretasInputs = document.querySelectorAll('input[type="radio"]:checked');

    perguntasInputs.forEach(input => {
        const index = parseInt(input.getAttribute('data-index'));
        currentQuestionario[index].pergunta = input.value;
    });

    alternativasInputs.forEach(input => {
        const index = parseInt(input.getAttribute('data-index'));
        const alt = input.getAttribute('data-alt');
        currentQuestionario[index].alternativas[alt.charCodeAt(0) - 97] = input.value;
    });

    corretasInputs.forEach(input => {
        const index = parseInt(input.name.split('-')[1]);
        currentQuestionario[index].correta = input.value;
    });

    // Enviar o questionário para o servidor
    fetch(`/salvar_questionario/${currentCandidatoId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ questionario: currentQuestionario })
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => { throw new Error(`Erro ao salvar questionário: ${text}`); });
        }
        return response.json();
    })
    .then(data => {
        console.log('Resposta do servidor:', data);
        alert('Questionário salvo com sucesso!');
        closeFormularioPopup();
    })
    .catch(err => {
        console.error('Erro:', err);
        alert(`Erro ao salvar questionário: ${err.message}`);
    });
}