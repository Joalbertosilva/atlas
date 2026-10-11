export default function PrivacyPage() {
  return (
    <article className="max-w-3xl space-y-4 text-sm leading-6 text-slate-700">
      <h1 className="text-xl font-semibold text-slate-900">Privacidade</h1>
      <p>
        Este painel trata dados públicos eleitorais agregados do TSE (resultados, cadastro de candidaturas e locais de
        votação) e geometrias do IBGE. Nomes de urna e de candidaturas são exibidos porque constam das bases públicas.
        CPF, e-mail, título de eleitor e data de nascimento não são importados nem exibidos.
      </p>
      <p>
        Consultas da busca integrada são encaminhadas a mecanismos de terceiros pelo servidor da aplicação, via instância
        própria do SearXNG. O texto da consulta não é colocado na URL desta interface. Não armazenamos histórico de
        buscas do usuário. Há cache de curta duração no servidor, com chave derivada (HMAC), sem guardar o texto da
        consulta. Não há perfis de opinião, cookies de rastreamento nem identificadores de publicidade.
      </p>
      <p>
        Os registros de acesso HTTP desta interface estão desligados (access_log off). Evite incluir dados pessoais na
        caixa de busca.
      </p>
      <p>
        Responsável pelo tratamento, canal de contato e fundamento jurídico: pendentes de definição pelo mantenedor.
      </p>
      <p>
        Esta página descreve práticas do software. Não afirma conformidade certificada com a LGPD nem qualquer selo de
        auditoria.
      </p>
    </article>
  )
}
