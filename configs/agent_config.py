# configs/agent_config.py

# app/agents/fallback_agent.py için config

# Fallback cevabı
FALLBACK_RESPONSE = "Üzgünüm, bu konuda size yardımcı olamıyorum. Sorunuz Resmi Gazete veya güncel haberler/genel bilgiler kapsamında değil gibi görünüyor veya isteğinizi şu anda işleyemiyorum."

# app/agents/news_agent.py için config

# Langchain Hub kullanılabiliyorsa, ReAct prompt'u oradan çekilmeye çalışılacak
# Eğer çekilemezse, manuel olarak oluşturulmuş prompt kullanılacak
LANGCHAIN_HUB_AVAILABLE = True

# Langchain Hub'dan çekilecek ReAct prompt'un path'i
REACT_HUB_PROMPT_PATH = "hwchase17/react"

# Eğer hub'dan çekemezsek, manuel olarak oluşturulmuş prompt template'i kullanılacak
MANUAL_REACT_PROMPT_TEMPLATE = """Aşağıdaki soruları olabildiğince iyi yanıtla. Şu araçlara erişimin var:

{tools}

Yanıtını oluşturmak için şu formatı kullan:

Soru: Yanıtlaman gereken soru
Düşünce: Yanıtı bulmak için ne yapman gerektiğini adım adım düşünmelisin. Hangi aracı kullanacağına karar ver. Araç kullanmak gerekmiyorsa doğrudan cevap verebilirsin.
Eylem: Kullanılacak aracın adı, şunlardan biri olmalı: [{tool_names}]
Eylem Girdisi: Araca verilecek girdi/sorgu.
Gözlem: Aracın döndürdüğü sonuç.
... (Bu Düşünce/Eylem/Eylem Girdisi/Gözlem döngüsü yanıtı bulana kadar veya bir limit dahilinde tekrarlanabilir)
Düşünce: Artık nihai yanıtı biliyorum ve bunu Türkçe olarak ifade edeceğim.
Nihai Yanıt: Orijinal soruya verilen nihai, kapsamlı ve konuşma dilinde **Türkçe** yanıt.

Şimdi başla!

Soru: {input}
Düşünce:{agent_scratchpad}""" 

# app/agents/resmi_gazete_agent.py için config

RESMI_GAZETE_COLLECTION = "resmi_gazete" 
# Sorgu başına RAG için kaç doküman çekileceği
NUM_DOCUMENTS_TO_RETRIEVE = 5
# LLM'e gönderilecek prompt şablonu
PROMPT_TEMPLATE = """Sen Resmi Gazete içerikleri konusunda uzman bir asistansın.
Sana verilen Resmi Gazete belgeleri bağlamını kullanarak aşağıdaki kullanıcı sorusunu cevapla.
Cevabın KESİNLİKLE sadece ve sadece sağlanan bağlamdaki bilgilere dayanmalıdır.
Eğer cevap verilen bağlamda bulunmuyorsa, "Sağlanan belgelerde bu bilgiye rastlanmamıştır." gibi bir ifade kullan.
Bağlam dışına çıkma, yorum yapma veya ek bilgi verme.

Kullanıcı Sorusu:
{query}

Resmi Gazete Belgeleri (Bağlam):
==============================
{context}
==============================

Cevap:"""

# app/agents/supervisor.py için config

from typing import List
# Yönlendirme için kullanılacak geçerli kategoriler
VALID_TARGET_CATEGORIES: List[str] = ["Resmi Gazete", "News", "Travel", "Other"]
# LLM geçerli bir kategori döndürmezse veya hata olursa varsayılan kategori
DEFAULT_TARGET_CATEGORY: str = "Other"
# Sorguyu sınıflandırmak için LLM'e verilen prompt.
CLASSIFICATION_PROMPT_TEMPLATE = """Görevin, aşağıda verilen kullanıcı sorgusunu analiz ederek şu üç kategoriden hangisine en uygun olduğunu belirlemektir: 

 1.  **Resmi Gazete**: Türkiye Cumhuriyeti Resmi Gazetesi'nde yayımlanan mevzuat (kanun, KHK, yönetmelik, tebliğ vb.), Cumhurbaşkanlığı Kararnameleri, Cumhurbaşkanlığı Genelgeleri, Cumhurbaşkanı Kararları (atama/görevden alma, yatırım programları, mali düzenlemeler, uluslararası anlaşmaların onayı vb.), yargı kararları (HSK, AYM vb.), TBMM kararları, ilanlar veya ilgili idari süreçler hakkında bilgi arayan sorular. 
     * Örnekler: "Son torba yasa ne zaman çıktı?", "Doğum Yardımı Yönetmeliği değişti mi?", "Resmi Gazete'de bugün hangi atamalar var?", "İş yerinde psikolojik tacizle ilgili yeni genelge yayımlandı mı?", "2025 Yılı Yatırım Programı açıklandı mı?"

 2.  **News**: Güncel olaylar, haberler (politika, ekonomi, spor, magazin vb.), genel kültür bilgisi (tarih, bilim, sanat vb.), tanımlar ("X nedir?"), hava durumu, finansal piyasa verileri (döviz, borsa), veya cevabı internette/Wikipedia'da bulunabilecek diğer tüm sorular. 
     * Örnekler: "İzmir'de yarın hava nasıl olacak?", "Enflasyon oranı yüzde kaç?", "Leonardo da Vinci kimdir?", "Türkiye'nin yüzölçümü ne kadar?", "Bugünkü maç sonuçları" 
     
 3.  **Travel**: Seyahat planlama, uçuşlar, oteller, destinasyonlar, güzergahlar, seyahat tavsiyeleri hakkında sorular.

 4.  **Other**: Yukarıdaki iki kategoriye girmeyen, genel sohbet ("Merhaba", "Nasılsın?", "İyi günler"), anlamsız veya eksik ifadeler ("asdf"), doğrudan talimatlar ("Bana kod yaz"), şaka/fıkra isteme gibi bu sistemin cevaplaması için tasarlanmamış diğer tüm sorgular. 

 Kullanıcı Sorgusu: 
 "{query}" 

 Bu sorguyu dikkatlice değerlendir ve YALNIZCA ve SADECE yukarıdaki üç kategori adından birini (Resmi Gazete, News, veya Other) cevap olarak ver. Başka hiçbir ek bilgi, açıklama veya giriş cümlesi yazma. 

 Kategori:""" 