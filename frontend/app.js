const API_URL = "";

let isRegisterMode = false;
let token = null;
let currentUser = null;
let todasConsultas = [];

// Elementos de Autenticação
const authSection = document.getElementById("auth-section");
const crudSection = document.getElementById("crud-section");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const authTitle = document.getElementById("auth-title");
const authSubmitBtn = document.getElementById("auth-submit-btn");
const authForm = document.getElementById("auth-form");
const authMessage = document.getElementById("auth-message");

// Elementos do CRUD da Clínica
const loggedUserSpan = document.getElementById("logged-user");
const logoutBtn = document.getElementById("logout-btn");
const consultaForm = document.getElementById("consulta-form");
const consultaIdInput = document.getElementById("consulta-id");
const pacienteInput = document.getElementById("paciente");
const contatoInput = document.getElementById("contato");
const medicoInput = document.getElementById("medico");
const dataHoraInput = document.getElementById("data-hora");
const statusInput = document.getElementById("status");
const saveBtn = document.getElementById("save-btn");
const cancelEditBtn = document.getElementById("cancel-edit-btn");
const buscaInput = document.getElementById("busca-input");
const crudMessage = document.getElementById("crud-message");
const consultasList = document.getElementById("consultas-list");

function setMessage(element, text, type = "") {
  element.textContent = text;
  element.className = `message ${type}`;
}

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatarDataHora(valorIso) {
  if (!valorIso || !valorIso.includes("T")) return valorIso;
  const [data, hora] = valorIso.split("T");
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}/${ano} às ${hora}`;
}

// Alternar abas Login / Cadastro
tabLogin.addEventListener("click", () => {
  isRegisterMode = false;
  tabLogin.classList.add("active");
  tabRegister.classList.remove("active");
  authTitle.textContent = "Acesso ao Sistema";
  authSubmitBtn.textContent = "Entrar";
  setMessage(authMessage, "");
});

tabRegister.addEventListener("click", () => {
  isRegisterMode = true;
  tabRegister.classList.add("active");
  tabLogin.classList.remove("active");
  authTitle.textContent = "Cadastrar Novo Atendente";
  authSubmitBtn.textContent = "Cadastrar";
  setMessage(authMessage, "");
});

// Envio do formulário de Login / Cadastro
authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const endpoint = isRegisterMode ? "/register" : "/login";

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      setMessage(authMessage, data.detail || "Erro na operação.", "error");
      return;
    }

    if (isRegisterMode) {
      setMessage(authMessage, "Atendente cadastrado! Faça login.", "success");
      tabLogin.click();
      authForm.reset();
    } else {
      token = data.token;
      currentUser = data.username;
      authForm.reset();
      mostrarPainelClinica();
    }
  } catch (err) {
    setMessage(authMessage, "Não foi possível conectar à API da clínica.", "error");
  }
});

// Logout
logoutBtn.addEventListener("click", async () => {
  if (token) {
    await fetch(`${API_URL}/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  token = null;
  currentUser = null;
  resetarFormulario();
  crudSection.classList.add("hidden");
  authSection.classList.remove("hidden");
  setMessage(authMessage, "");
  setMessage(crudMessage, "");
});

function mostrarPainelClinica() {
  authSection.classList.add("hidden");
  crudSection.classList.remove("hidden");
  loggedUserSpan.textContent = currentUser;
  carregarConsultas();
}

async function carregarConsultas() {
  try {
    const response = await fetch(`${API_URL}/consultas`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.status === 401) {
      logoutBtn.click();
      setMessage(authMessage, "Sessão expirada. Entre novamente.", "error");
      return;
    }

    todasConsultas = await response.json();
    aplicarFiltro();
  } catch (err) {
    setMessage(crudMessage, "Erro ao carregar agendamentos.", "error");
  }
}

buscaInput.addEventListener("input", aplicarFiltro);

function aplicarFiltro() {
  const termo = buscaInput.value.trim().toLowerCase();
  if (!termo) {
    renderizarTabela(todasConsultas);
    return;
  }

  const filtradas = todasConsultas.filter(
    (c) =>
      c.paciente.toLowerCase().includes(termo) ||
      c.medico.toLowerCase().includes(termo) ||
      c.status.toLowerCase().includes(termo)
  );
  renderizarTabela(filtradas);
}

function renderizarTabela(lista) {
  consultasList.innerHTML = "";

  if (lista.length === 0) {
    consultasList.innerHTML = `<tr><td colspan="7">Nenhuma consulta encontrada.</td></tr>`;
    return;
  }

  lista.forEach((consulta) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${consulta.id}</td>
      <td><strong>${escapeHTML(consulta.paciente)}</strong></td>
      <td>${escapeHTML(consulta.contato)}</td>
      <td>${escapeHTML(consulta.medico)}</td>
      <td>${escapeHTML(formatarDataHora(consulta.data_hora))}</td>
      <td><span class="badge ${escapeHTML(consulta.status)}">${escapeHTML(consulta.status)}</span></td>
      <td class="actions-cell">
        <button type="button" class="btn warning btn-sm btn-edit">Editar</button>
        <button type="button" class="btn danger btn-sm btn-delete">Excluir</button>
      </td>
    `;

    tr.querySelector(".btn-edit").addEventListener("click", () => {
      prepararEdicao(consulta);
    });

    tr.querySelector(".btn-delete").addEventListener("click", () => {
      deletarConsulta(consulta.id);
    });

    consultasList.appendChild(tr);
  });
}

// Criar ou Atualizar Consulta
consultaForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = consultaIdInput.value;

  const payload = {
    paciente: pacienteInput.value.trim(),
    contato: contatoInput.value.trim(),
    medico: medicoInput.value.trim(),
    data_hora: dataHoraInput.value,
    status: statusInput.value,
  };

  const method = id ? "PUT" : "POST";
  const url = id ? `${API_URL}/consultas/${id}` : `${API_URL}/consultas`;

  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json();
      setMessage(crudMessage, errData.detail || "Erro ao salvar consulta.", "error");
      return;
    }

    setMessage(
      crudMessage,
      id ? "Agendamento atualizado com sucesso!" : "Consulta agendada com sucesso!",
      "success"
    );
    resetarFormulario();
    carregarConsultas();
  } catch (err) {
    setMessage(crudMessage, "Erro de conexão com o servidor.", "error");
  }
});

function prepararEdicao(consulta) {
  consultaIdInput.value = consulta.id;
  pacienteInput.value = consulta.paciente;
  contatoInput.value = consulta.contato;
  medicoInput.value = consulta.medico;
  dataHoraInput.value = consulta.data_hora;
  statusInput.value = consulta.status;
  saveBtn.textContent = "Salvar Alterações";
  cancelEditBtn.classList.remove("hidden");
}

cancelEditBtn.addEventListener("click", resetarFormulario);

function resetarFormulario() {
  consultaForm.reset();
  consultaIdInput.value = "";
  saveBtn.textContent = "Agendar Consulta";
  cancelEditBtn.classList.add("hidden");
}

async function deletarConsulta(id) {
  try {
    const response = await fetch(`${API_URL}/consultas/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.ok) {
      setMessage(crudMessage, "Agendamento excluído.", "success");
      carregarConsultas();
    }
  } catch (err) {
    setMessage(crudMessage, "Erro ao excluir agendamento.", "error");
  }
}
