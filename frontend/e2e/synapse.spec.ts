import { expect, test, type Page } from "@playwright/test";

import { readQaRunState, type QaAccount } from "./support/qa-state";

const maxUploadSizeBytes = 10 * 1024 * 1024;
const qaFilename = "registro-qa-synapse.txt";

test.describe.configure({ mode: "serial" });

test("homologa ingestão, segurança e isolamento da base documental", async ({ browser, request }) => {
  const { accountA, accountB } = readQaRunState().accounts;
  const accountAContext = await browser.newContext({ acceptDownloads: true });
  const accountAPage = await accountAContext.newPage();

  await test.step("bloqueia uma API sem sessão autenticada", async () => {
    const response = await request.get(`${requiredApiUrl()}/api/documents`);
    expect(response.status()).toBe(401);
  });

  await test.step("cria uma sessão para a primeira conta de QA", async () => {
    await signIn(accountAPage, accountA);
  });

  await test.step("rejeita um arquivo acima de 10 MB antes do envio", async () => {
    await accountAPage.goto("/upload");
    await accountAPage.locator('input[type="file"]').setInputFiles({
      name: "arquivo-acima-do-limite.txt",
      mimeType: "text/plain",
      buffer: Buffer.alloc(maxUploadSizeBytes + 1, "a"),
    });
    await expect(
      accountAPage.getByText("O arquivo excede o limite de 10 MB desta fase."),
    ).toBeVisible();
  });

  await test.step("informa uma falha amigável para formato não suportado", async () => {
    await accountAPage.locator('input[type="file"]').setInputFiles({
      name: "arquivo-invalido.exe",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("arquivo de teste", "utf8"),
    });
    await accountAPage.getByRole("button", { name: "Processar documento" }).click();
    await expect(
      accountAPage.getByText("Formato ainda não suportado nesta fase."),
    ).toBeVisible();
  });

  await test.step("processa, lista e baixa um documento válido", async () => {
    await accountAPage.locator('input[type="file"]').setInputFiles({
      name: qaFilename,
      mimeType: "text/plain",
      buffer: Buffer.from(
        "Registro de QA do Synapse AI. O documento é privado, temporário e usado somente na homologação automatizada.",
        "utf8",
      ),
    });
    await accountAPage.getByRole("button", { name: "Processar documento" }).click();
    await expect(accountAPage.getByText(/Documento processado e salvo/)).toBeVisible();

    const documentCard = accountAPage.locator("article").filter({ hasText: qaFilename });
    await expect(documentCard).toBeVisible();
    const downloadPromise = accountAPage.waitForEvent("download");
    await documentCard.getByRole("button", { name: "Baixar original" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(qaFilename);
  });

  await test.step("garante que a segunda conta não enxerga dados da primeira", async () => {
    const accountBContext = await browser.newContext();
    const accountBPage = await accountBContext.newPage();
    await signIn(accountBPage, accountB);
    await accountBPage.goto("/upload");
    await expect(accountBPage.getByText("Sua base documental está vazia.")).toBeVisible();
    await expect(accountBPage.getByText(qaFilename)).toHaveCount(0);
    await accountBContext.close();
  });

  await accountAContext.close();
});

test("consulta o Copiloto real e apresenta uma resposta completa", async ({ browser }) => {
  test.skip(process.env.E2E_RUN_COPILOT === "false", "Copiloto desativado para esta execução.");

  const { accountA } = readQaRunState().accounts;
  const context = await browser.newContext();
  const page = await context.newPage();
  const prompt = "Qual é a finalidade do Synapse AI?";

  await signIn(page, accountA);
  await page.getByRole("button", { name: "Copiloto Synapse" }).click();
  await page.getByPlaceholder("Pergunte ao Copiloto").fill(prompt);
  await page.getByRole("button", { name: "Enviar" }).click();

  await expect(page.getByTestId("copilot-message").filter({ hasText: prompt })).toBeVisible();
  const assistantMessages = page.locator('[data-testid="copilot-message"][data-role="assistant"]');
  await expect(assistantMessages).toHaveCount(2);
  await expect(assistantMessages.last()).not.toHaveText(
    "Não consegui completar a resposta neste momento. Verifique a conexão com a API e tente novamente.",
  );

  await context.close();
});

async function signIn(page: Page, account: QaAccount): Promise<void> {
  await page.goto("/dashboard");
  await expect(page.getByLabel("E-mail")).toBeVisible();
  await page.getByLabel("E-mail").fill(account.email);
  await page.getByLabel("Senha").fill(account.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dashboard executivo" })).toBeVisible();
}

function requiredApiUrl(): string {
  const apiUrl = process.env.E2E_API_URL?.replace(/\/$/, "");
  if (!apiUrl) {
    throw new Error("A variável E2E_API_URL precisa ser definida em .env.e2e.");
  }
  return apiUrl;
}
