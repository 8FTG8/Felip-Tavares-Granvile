/**
 * Interface da solução de manutenção prescritiva (ADR-002).
 *
 * Cliente da API, não uma segunda implementação da lógica: todas as telas conversam com os
 * mesmos endpoints que um supervisório ou um CMMS usaria. Nenhuma regra de decisão vive
 * aqui — o que a tela mostra é o que o serviço respondeu.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "./api/cliente";
import type { CoberturaDocumental, EstadoSistema, PainelHistorico } from "./api/tipos";
import { BarraLateral } from "./componentes/navegacao";
import { useTema } from "./tema";
import type { Pagina } from "./componentes/navegacao";
import { Analise } from "./paginas/Analise";
import { Assistente } from "./paginas/Assistente";
import { Documentos } from "./paginas/Documentos";
import { Painel } from "./paginas/Painel";

export default function App() {
  const { tema, alternar } = useTema();
  const [pagina, setPagina] = useState<Pagina>("painel");
  const [sistema, setSistema] = useState<EstadoSistema | null>(null);
  const [estatisticas, setEstatisticas] = useState<PainelHistorico | null>(null);
  const [cobertura, setCobertura] = useState<CoberturaDocumental[]>([]);

  const [carregando, setCarregando] = useState(true);
  const [apiFora, setApiFora] = useState(false);

  /**
   * Recarrega o estado compartilhado — no início e após cadastrar um documento.
   *
   * A falha é registrada explicitamente, e não engolida: sem isso, uma API fora do ar
   * deixaria o painel em carregamento indefinido, que na tela é indistinguível de um
   * sistema travado.
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

  return (
    <div className="flex min-h-screen">
      <BarraLateral
        atual={pagina}
        aoNavegar={setPagina}
        sistema={sistema}
        cobertura={cobertura}
        tema={tema}
        aoAlternarTema={alternar}
      />

      {/* As telas permanecem montadas e apenas ocultas: alternar entre elas durante a
          apresentação não pode apagar a conversa do assistente nem o resultado da análise. */}
      <main className="flex-1 min-w-0 px-8 py-7">
        <div className="max-w-[1400px] mx-auto">
          <div hidden={pagina !== "painel"}>
            <Painel
              dados={estatisticas}
              sistema={sistema}
              carregando={carregando}
              apiFora={apiFora}
              aoNavegar={setPagina}
            />
          </div>
          <div hidden={pagina !== "analise"}>
            <Analise sistema={sistema} />
          </div>
          <div hidden={pagina !== "assistente"}>
            <Assistente sistema={sistema} />
          </div>
          <div hidden={pagina !== "documentos"}>
            <Documentos cobertura={cobertura} sistema={sistema} aoCadastrar={carregar} />
          </div>
        </div>
      </main>
    </div>
  );
}
