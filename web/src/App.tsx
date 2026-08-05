/**
 * Interface da solução de manutenção prescritiva (ADR-002).
 *
 * Cliente da API, não uma segunda implementação da lógica: todas as telas conversam
 * com os mesmos endpoints que um supervisório ou um CMMS usaria. Nenhuma regra de
 * decisão vive aqui — o que a tela mostra é o que o serviço respondeu.
 *
 * O produto ocupa a janela inteira, sem moldura: a lateral escura sangra até a borda
 * e a área de trabalho recebe todo o resto. É o arranjo de uma ferramenta que fica
 * aberta o dia todo — margem decorativa em volta cobraria largura de tabela em troca
 * de nada.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "./api/cliente";
import type { CoberturaDocumental, EstadoSistema, PainelHistorico } from "./api/tipos";
import { BarraLateral, BarraMovel } from "./componentes/navegacao";
import type { Pagina } from "./componentes/navegacao";
import { Analise } from "./paginas/Analise";
import { Assistente } from "./paginas/Assistente";
import { Documentos } from "./paginas/Documentos";
import { Painel } from "./paginas/Painel";

export default function App() {
  const [pagina, setPagina] = useState<Pagina>("painel");
  const [menuAberto, setMenuAberto] = useState(false);
  /**
   * Condição que a análise recusou e que o usuário pediu para cadastrar.
   *
   * Existe para fechar o ciclo do ADR-014 sem que ninguém precise reencontrar a
   * condição num menu de doze: recusou, clicou, o cadastro já abre apontando para
   * ela. É limpa em qualquer navegação comum — mantê-la faria uma visita posterior a
   * Documentos abrir numa condição escolhida em outro contexto.
   */
  const [condicaoParaCadastro, setCondicaoParaCadastro] = useState<string | null>(null);
  const [sistema, setSistema] = useState<EstadoSistema | null>(null);
  const [estatisticas, setEstatisticas] = useState<PainelHistorico | null>(null);
  const [cobertura, setCobertura] = useState<CoberturaDocumental[]>([]);

  const [carregando, setCarregando] = useState(true);
  const [apiFora, setApiFora] = useState(false);

  /**
   * Recarrega o estado compartilhado — no início e após cadastrar um documento.
   *
   * A falha é registrada explicitamente, e não engolida: sem isso, uma API fora do
   * ar deixaria o painel em carregamento indefinido, que na tela é indistinguível de
   * um sistema travado.
   */
  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      const [novoSistema, novasEstatisticas, novaCobertura] = await Promise.all([
        api.sistema(),
        api.estatisticas(),
        api.cobertura(),
      ]);
      setSistema(novoSistema);
      setEstatisticas(novasEstatisticas);
      setCobertura(novaCobertura);
      setApiFora(false);
    } catch {
      setApiFora(true);
      setSistema(null);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  /** Navegar fecha a gaveta: em tela estreita ela cobre o conteúdo que se pediu. */
  function navegar(destino: Pagina) {
    setPagina(destino);
    setMenuAberto(false);
    setCondicaoParaCadastro(null);
  }

  /** Leva ao cadastro com a condição recusada já selecionada. */
  function cadastrarCondicao(condicao: string) {
    setPagina("documentos");
    setMenuAberto(false);
    setCondicaoParaCadastro(condicao);
  }

  return (
    <div className="flex min-h-screen">
      <BarraLateral
        atual={pagina}
        aoNavegar={navegar}
        sistema={sistema}
        cobertura={cobertura}
        aberta={menuAberto}
        aoFechar={() => setMenuAberto(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col bg-fundo">
        <BarraMovel aoAbrir={() => setMenuAberto(true)} />

        {/* As telas permanecem montadas e apenas ocultas: alternar entre elas
            durante a apresentação não pode apagar a conversa do assistente nem o
            resultado da análise. */}
        <main className="flex-1 px-4 py-5 sm:px-6 lg:px-7 lg:py-6">
          <div className="max-w-[var(--largura-conteudo)] mx-auto">
            <div hidden={pagina !== "painel"}>
              <Painel
                dados={estatisticas}
                sistema={sistema}
                carregando={carregando}
                apiFora={apiFora}
                aoNavegar={navegar}
              />
            </div>
            <div hidden={pagina !== "analise"}>
              <Analise sistema={sistema} aoCadastrar={cadastrarCondicao} />
            </div>
            <div hidden={pagina !== "assistente"}>
              <Assistente sistema={sistema} />
            </div>
            <div hidden={pagina !== "documentos"}>
              <Documentos
                cobertura={cobertura}
                sistema={sistema}
                aoCadastrar={carregar}
                condicaoInicial={condicaoParaCadastro}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
