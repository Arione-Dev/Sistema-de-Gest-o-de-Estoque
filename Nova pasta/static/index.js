







console.log('Carregando index.js...');

let currentProduto = null;
let produtosMassivo = []; // Array para armazenar produtos no modo ajuste em massivo
let ultimoCodigoBipado = null; // Armazena o último código bipado para comparação
let ajustesPendentes = []; // Array para armazenar ajustes pendentes

function atualizarAjusteMassivo() {
    const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
    if (ajusteMassivoCheckbox.checked) {
        console.log('Ajuste em Massivo ativado.');
        produtosMassivo = []; // Reseta a lista de produtos acumulados
        ultimoCodigoBipado = null; // Reseta o último código bipado
        document.getElementById('ajusteInput').value = '0'; // Quantidade inicial zero
    } else {
        console.log('Ajuste em Massivo desativado.');
        produtosMassivo = []; // Limpa a lista ao desativar o modo massivo
        ultimoCodigoBipado = null; // Reseta o último código bipado
        document.getElementById('ajusteInput').value = '0'; // Reseta o campo de quantidade
    }
}

function atualizarAjusteMassa() {
    const ajusteMenosCheckbox = document.getElementById('ajusteMenosCheckbox');
    const ajusteMaisCheckbox = document.getElementById('ajusteMaisCheckbox');
    const btnMenos = document.querySelector('.btn-menos');
    const btnMais = document.querySelector('.btn-mais');

    console.log(`Atualizar Ajuste Massa - Ajuste Menos: ${ajusteMenosCheckbox.checked}, Ajuste Mais: ${ajusteMaisCheckbox.checked}`);

    if (ajusteMenosCheckbox.checked && ajusteMaisCheckbox.checked) {
        ajusteMaisCheckbox.checked = false;
    }

    if (ajusteMenosCheckbox.checked) {
        btnMenos.disabled = false;
        btnMais.disabled = true;
    } else if (ajusteMaisCheckbox.checked) {
        btnMenos.disabled = true;
        btnMais.disabled = false;
    } else {
        btnMenos.disabled = false;
        btnMais.disabled = false;
    }
}

function atualizarOcultarTeclado() {
    const ocultarTecladoCheckbox = document.getElementById('ocultarTecladoCheckbox');
    const codigoInput = document.getElementById('codigoInput');

    if (ocultarTecladoCheckbox.checked) {
        console.log('Ocultar Teclado ativado.');
        codigoInput.setAttribute('inputmode', 'none');
        codigoInput.focus();
    } else {
        console.log('Ocultar Teclado desativado.');
        codigoInput.removeAttribute('inputmode');
        codigoInput.focus();
    }
}

function formatarQuantidade() {
    const ajusteMenosCheckbox = document.getElementById('ajusteMenosCheckbox');
    const ajusteMaisCheckbox = document.getElementById('ajusteMaisCheckbox');
    let quantidade = parseInt(document.getElementById('ajusteInput').value) || 0;

    console.log(`Formatar Quantidade - Quantidade atual: ${quantidade}, Ajuste Menos: ${ajusteMenosCheckbox.checked}, Ajuste Mais: ${ajusteMaisCheckbox.checked}`);

    quantidade = Math.abs(quantidade);

    if (ajusteMenosCheckbox.checked) {
        document.getElementById('ajusteInput').value = -quantidade;
    } else {
        document.getElementById('ajusteInput').value = quantidade;
    }
    console.log(`Quantidade formatada para: ${document.getElementById('ajusteInput').value}`);
}

async function buscarProduto() {
    console.log('Executando buscarProduto()');
    const codigo = document.getElementById('codigoInput').value.trim();
    console.log(`Buscando produto com código: ${codigo}`);

    if (!codigo) {
        console.log('Código não fornecido.');
        alert('Por favor, insira o código ou barras do produto.');
        return;
    }

    try {
        console.log(`Enviando requisição GET para /produto/${codigo}`);
        const response = await fetch(`/produto/${codigo}`);
        console.log('Resposta recebida do backend:', response);

        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Erro na requisição: ${response.status} ${response.statusText} - ${JSON.stringify(errorData)}`);
            throw new Error(errorData.error || `Erro na requisição: ${response.status} ${response.statusText}`);
        }

        const produto = await response.json();
        console.log('Produto retornado do backend:', produto);
        currentProduto = produto;

        document.getElementById('produtoInfo').innerHTML = `
            <p>Código: ${produto.codigo}</p>
            <p>Descrição: ${produto.descricao || 'Descrição não disponível'}</p>
            <p>Saldo Atual: ${produto.saldo_atual !== undefined ? produto.saldo_atual : 'N/A'}</p>
            <p>Barras: ${produto.barras || 'N/A'}</p>
        `;
        document.getElementById('ajusteForm').style.display = 'block';

        const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
        if (!ajusteMassivoCheckbox.checked) {
            document.getElementById('ajusteInput').value = '0';
        } else if (ultimoCodigoBipado !== codigo) {
            document.getElementById('ajusteInput').value = '1'; // Quantidade padrão para novo código
        }

        document.getElementById('codigoInput').value = '';
        ultimoCodigoBipado = codigo;
        carregarHistorico();
    } catch (err) {
        console.error('Erro ao buscar produto:', err);
        alert(`Erro ao buscar produto: ${err.message}`);
        document.getElementById('produtoInfo').innerHTML = '';
        document.getElementById('ajusteForm').style.display = 'none';
        currentProduto = null;
        document.getElementById('codigoInput').value = '';
    }
}

async function processarCodigoBarras(codigo) {
    if (!codigo) {
        console.log('Nenhum código fornecido para processar.');
        return;
    }

    try {
        console.log(`Processando código de barras: ${codigo}`);
        const response = await fetch(`/produto/${codigo}`);
        const produto = await response.json();
        if (produto.error) {
            throw new Error(produto.error);
        }

        currentProduto = produto;

        const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
        if (ajusteMassivoCheckbox.checked) {
            const ajusteMenosCheckbox = document.getElementById('ajusteMenosCheckbox');
            const ajusteMaisCheckbox = document.getElementById('ajusteMaisCheckbox');

            console.log('Ajuste em Massivo ativo. Ajuste Menos:', ajusteMenosCheckbox.checked, 'Ajuste Mais:', ajusteMaisCheckbox.checked);

            // Verifica se o produto já está na lista de produtos massivos
            let produtoExistente = produtosMassivo.find(p => p.codigo === produto.codigo);

            if (!produtoExistente || ultimoCodigoBipado !== codigo) {
                // Novo produto ou novo bip após mudança de código
                produtoExistente = { codigo: produto.codigo, quantidade: 0 };
                if (!produtosMassivo.find(p => p.codigo === produto.codigo)) {
                    produtosMassivo.push(produtoExistente);
                }
            }

            // Incrementa a quantidade para o bip atual
            produtoExistente.quantidade += 1;

            // Calcula a quantidade total para exibição
            const quantidadeTotal = produtoExistente.quantidade;
            document.getElementById('ajusteInput').value = ajusteMenosCheckbox.checked ? -quantidadeTotal : quantidadeTotal;

            console.log('Produtos acumulados:', produtosMassivo);
            console.log('Quantidade atualizada no campo:', document.getElementById('ajusteInput').value);

            ultimoCodigoBipado = codigo;

            document.getElementById('produtoInfo').innerHTML = `
                <p>Código: ${produto.codigo}</p>
                <p>Descrição: ${produto.descricao || 'Descrição não disponível'}</p>
                <p>Saldo Atual: ${produto.saldo_atual !== undefined ? produto.saldo_atual : 'N/A'}</p>
                <p>Barras: ${produto.barras || 'N/A'}</p>
            `;
            document.getElementById('ajusteForm').style.display = 'block';
        }

        document.getElementById('codigoInput').value = '';
    } catch (err) {
        console.error('Erro ao processar código de barras:', err);
        alert('Erro ao processar código de barras: ' + err.message);
        document.getElementById('codigoInput').value = '';
    }
}

function alterarQuantidade(operacao) {
    const ajusteMenosCheckbox = document.getElementById('ajusteMenosCheckbox');
    const ajusteMaisCheckbox = document.getElementById('ajusteMaisCheckbox');
    let quantidade = parseInt(document.getElementById('ajusteInput').value) || 0;

    console.log(`Alterar quantidade - Operação: ${operacao}, Quantidade atual: ${quantidade}, Ajuste Menos: ${ajusteMenosCheckbox.checked}, Ajuste Mais: ${ajusteMaisCheckbox.checked}`);

    if (ajusteMenosCheckbox.checked && operacao !== 'menos') {
        alert('Apenas ajustes de diminuição são permitidos com "Ajuste Menos" marcado.');
        return;
    }
    if (ajusteMaisCheckbox.checked && operacao !== 'mais') {
        alert('Apenas ajustes de aumento são permitidos com "Ajuste Mais" marcado.');
        return;
    }

    if (operacao === 'mais') {
        quantidade += 1;
    } else if (operacao === 'menos') {
        quantidade -= 1;
    }

    document.getElementById('ajusteInput').value = quantidade;
    console.log(`Quantidade atualizada para: ${quantidade}`);
}

function adicionarAjuste() {
    if (!currentProduto) {
        console.log('Nenhum produto selecionado para adicionar ao ajuste.');
        alert('Nenhum produto selecionado para adicionar ao ajuste.');
        return;
    }

    let quantidade = parseInt(document.getElementById('ajusteInput').value);
    console.log('Quantidade digitada:', quantidade);
    if (isNaN(quantidade) || quantidade === 0) {
        console.log('Quantidade inválida:', quantidade);
        alert('Por favor, digite uma quantidade válida.');
        return;
    }

    const ajusteExistente = ajustesPendentes.find(ajuste => ajuste.codigo === currentProduto.codigo);
    if (ajusteExistente) {
        ajusteExistente.quantidade += quantidade;
        console.log(`Produto ${currentProduto.codigo} já existe na lista. Nova quantidade: ${ajusteExistente.quantidade}`);
    } else {
        ajustesPendentes.push({
            codigo: currentProduto.codigo,
            descricao: currentProduto.descricao || 'Descrição não disponível',
            quantidade: quantidade
        });
        console.log(`Produto ${currentProduto.codigo} adicionado à lista com quantidade: ${quantidade}`);
    }

    // Reseta o estado do modo massivo para o produto atual
    const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
    if (ajusteMassivoCheckbox.checked) {
        produtosMassivo = produtosMassivo.filter(p => p.codigo !== currentProduto.codigo); // Remove o produto ajustado
        document.getElementById('ajusteInput').value = '0'; // Reseta a quantidade exibida
        ultimoCodigoBipado = null; // Permite que o próximo bip reinicie a contagem
    } else {
        document.getElementById('ajusteInput').value = '0'; // Reseta para modo normal
    }

    atualizarListaPendentes();
}

function atualizarListaPendentes() {
    const tbody = document.getElementById('pendentesBody');
    tbody.innerHTML = '';
    ajustesPendentes.forEach(ajuste => {
        const tr = document.createElement('tr');
        const ajusteSymbol = ajuste.quantidade > 0 ? '+' : '';
        tr.innerHTML = `
            <td>${ajuste.codigo}</td>
            <td>${ajuste.descricao}</td>
            <td>${ajusteSymbol}${ajuste.quantidade}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function confirmarAjuste() {
    if (ajustesPendentes.length === 0) {
        console.log('Nenhum ajuste pendente para confirmar.');
        alert('Nenhum ajuste pendente para confirmar.');
        return;
    }

    for (const ajuste of ajustesPendentes) {
        if (!ajuste.codigo || ajuste.codigo.trim() === '') {
            console.log('Erro: Um ajuste na lista não possui um código válido:', ajuste);
            alert('Erro: Um ou mais ajustes na lista não possuem um código válido.');
            return;
        }
        if (!ajuste.descricao || ajuste.descricao.trim() === '') {
            console.log('Aviso: Descrição não fornecida para o ajuste, usando valor padrão:', ajuste);
            ajuste.descricao = 'Descrição não disponível';
        }
        if (!ajuste.quantidade || isNaN(ajuste.quantidade)) {
            console.log('Erro: Quantidade inválida no ajuste:', ajuste);
            alert('Erro: Um ou mais ajustes na lista possuem uma quantidade inválida.');
            return;
        }
    }

    try {
        console.log('Enviando requisição POST para /ajustar-estoque');
        console.log('Ajustes pendentes enviados:', JSON.stringify(ajustesPendentes, null, 2));
        const response = await fetch('/ajustar-estoque', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ajustes: ajustesPendentes })
        });
        console.log('Resposta recebida do backend:', response);

        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Erro na requisição: ${response.status} ${response.statusText} - ${JSON.stringify(errorData)}`);
            throw new Error(errorData.error || `Erro na requisição: ${response.status} ${response.statusText}`);
        }

        const resultado = await response.json();
        console.log('Resultado retornado do backend:', resultado);

        if (resultado.success) {
            let mensagem = `Ajuste #${resultado.numero_ajuste} realizado com sucesso!\n`;
            resultado.resultados.forEach(res => {
                mensagem += `Código: ${res.codigo}, Novo Saldo: ${res.saldo_atual}\n`;
            });
            alert(mensagem);

            ajustesPendentes = [];
            atualizarListaPendentes();
            document.getElementById('produtoInfo').innerHTML = '';
            document.getElementById('ajusteForm').style.display = 'none';
            currentProduto = null;
            produtosMassivo = [];
            ultimoCodigoBipado = null;
            carregarHistorico();
        } else {
            throw new Error('Erro ao realizar ajustes');
        }
    } catch (err) {
        console.error('Erro ao ajustar estoque:', err);
        alert(`Erro ao ajustar estoque: ${err.message}`);
    }
}

async function carregarHistorico() {
    console.log('Executando carregarHistorico()');
    try {
        console.log('Enviando requisição GET para /historico');
        const response = await fetch('/historico');
        console.log('Resposta recebida do backend:', response);

        if (!response.ok) {
            const errorData = await response.json();
            console.error(`Erro na requisição: ${response.status} ${response.statusText} - ${JSON.stringify(errorData)}`);
            throw new Error(errorData.error || `Erro na requisição: ${response.status} ${response.statusText}`);
        }

        const historico = await response.json();
        console.log('Histórico retornado do backend:', historico);

        const tbody = document.getElementById('historicoBody');
        tbody.innerHTML = '';
        historico.forEach(item => {
            const tr = document.createElement('tr');
            const ajusteIcon = item.ajuste > 0 ? 'positive' : 'negative';
            const ajusteSymbol = item.ajuste > 0 ? '+' : '-';
            tr.innerHTML = `
                <td><span class="ajuste-icon ${ajusteIcon}">${ajusteSymbol}</span></td>
                <td>${item.id}</td>
                <td>${item.produto_codigo}</td>
                <td>${item.descricao || 'N/A'}</td>
                <td>${ajusteSymbol}${item.ajuste}</td>
                <td>${item.data_hora}</td>
                <td>${item.matricula || 'N/A'}</td>
                <td>${item.nome_usuario || 'N/A'}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Erro ao carregar histórico:', err);
        alert(`Erro ao carregar histórico: ${err.message}`);
    }
}

const codigoInput = document.getElementById('codigoInput');

codigoInput.addEventListener('keydown', (event) => {
    console.log('Evento keydown detectado no codigoInput. Tecla:', event.key, 'Código:', event.keyCode);
    if (event.keyCode === 13 || event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        console.log('Enter bloqueado no codigoInput via keydown.');
        const codigo = event.target.value.trim();
        if (codigo) {
            console.log('Código detectado via Enter:', codigo);
            const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
            if (ajusteMassivoCheckbox.checked) {
                processarCodigoBarras(codigo);
            } else {
                buscarProduto();
            }
        }
    }
});

codigoInput.addEventListener('keypress', (event) => {
    console.log('Evento keypress detectado no codigoInput. Tecla:', event.key, 'Código:', event.keyCode);
    if (event.keyCode === 13 || event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        console.log('Enter bloqueado no codigoInput via keypress.');
    }
});

codigoInput.addEventListener('input', (event) => {
    const codigo = event.target.value.trim();
    console.log('Evento input detectado no codigoInput. Código no campo:', codigo);
    if (codigo && (codigo.endsWith('\n') || codigo.length >= 8)) {
        console.log('Código de barras detectado via input no codigoInput:', codigo);
        event.target.value = codigo.replace(/\n/g, '');
        const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
        setTimeout(() => {
            if (ajusteMassivoCheckbox.checked) {
                processarCodigoBarras(codigo);
            } else {
                buscarProduto();
            }
        }, 0);
    }
});

codigoInput.addEventListener('change', (event) => {
    const codigo = event.target.value.trim();
    console.log('Evento change detectado no codigoInput. Código no campo:', codigo);
    if (codigo) {
        console.log('Código de barras detectado via change no codigoInput:', codigo);
        event.target.value = codigo.replace(/\n/g, '');
        const ajusteMassivoCheckbox = document.getElementById('ajusteMassivoCheckbox');
        setTimeout(() => {
            if (ajusteMassivoCheckbox.checked) {
                processarCodigoBarras(codigo);
            } else {
                buscarProduto();
            }
        }, 0);
    }
});

document.getElementById('ajusteInput').addEventListener('input', () => {
    formatarQuantidade();
});

document.addEventListener('DOMContentLoaded', () => {
    console.log('Página carregada. Executando carregarHistorico().');
    carregarHistorico();
    document.getElementById('codigoInput').focus();
});

console.log('index.js carregado com sucesso.');