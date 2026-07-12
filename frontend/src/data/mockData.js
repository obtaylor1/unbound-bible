/**
 * Mock Data for The Unbound Bible Research Platform
 * Grounded in scholarly, multi-canonical, and historical research.
 */

// 1. Factbook-style Research Topics
export const MOCK_RESEARCH_TOPICS = {
  "moses": {
    slug: "moses",
    name: "Moses",
    type: "person",
    summary: "Moses was a seminal prophet, leader, and lawgiver in the Hebrew Bible. Born in Egypt, raised in Pharaoh's court, and exiled to Midian, he was called by Yahweh at the burning bush to deliver the Israelites from slavery. He led them through the Exodus, mediated the covenant at Mount Sinai (Horeb), and guided them through the wilderness for forty years. In the Ethiopian Orthodox tradition, Moses is also linked historically to the Red Sea crossings and early Cushite relations described in Numbers 12.",
    scriptureReferences: ["Exodus 2:1-10", "Exodus 3:1-12", "Numbers 12:1-3", "Deuteronomy 34:1-12", "Acts 7:20-44", "Hebrews 11:23-29"],
    timelineEvents: [
      { year: "c. 1526 BC", event: "Born in Egypt and placed in a papyrus basket in the Nile." },
      { year: "c. 1486 BC", event: "Flees Egypt to Midian after slaying an Egyptian taskmaster." },
      { year: "c. 1446 BC", event: "Encounters the Burning Bush; confronts Pharaoh; leads Israel out of Egypt." },
      { year: "c. 1445 BC", event: "Receives the Ten Commandments and covenant laws at Mount Sinai." },
      { year: "c. 1406 BC", event: "Passes away on Mount Nebo overlooking the Promised Land at age 120." }
    ],
    geographicalMaps: [
      { name: "Goshen (Egypt)", description: "The fertile land where Israelites resided during their bondage.", lat: 30.85, lng: 31.82 },
      { name: "Mount Sinai", description: "The mountain of God where the Law was given.", lat: 28.539, lng: 33.975 },
      { name: "Mount Nebo", description: "Where Moses viewed the Promised Land and died.", lat: 31.765, lng: 35.726 }
    ],
    relatedPeople: ["Aaron", "Miriam", "Joshua", "Jethro (Reuel)", "Pharaoh", "Zipporah"],
    relatedPlaces: ["Egypt", "Red Sea", "Midian", "Mount Horeb", "Kadesh-Barnea", "Moab"],
    themes: ["Covenant", "Deliverance", "Law (Torah)", "Prophecy", "Intercession"],
    originalWords: [
      { word: "מֹשֶׁה", lang: "Hebrew", strong: "H4872", def: "Mosheh - meaning 'drawn out' (of water)." },
      { word: "Μωϋσῆς", lang: "Greek", strong: "G3475", def: "Mōysēs - Greek transliteration of Moses." },
      { word: "ሙሴ", lang: "Ge'ez", strong: "N/A", def: "Musē - The Ge'ez name of the prophet." }
    ],
    manuscripts: [
      { name: "Dead Sea Scrolls (4Q364)", lang: "Hebrew", date: "c. 2nd c. BC", details: "Fragments of the Pentateuch preserving Moses' speeches." },
      { name: "Ge'ez Octateuch (EOTC Codex)", lang: "Ge'ez", date: "15th c. AD", details: "Contains the canonical books of Moses including Jubilees." },
      { name: "Samaritan Pentateuch", lang: "Samaritan Hebrew", date: "c. 11th c. AD", details: "Preserves the distinct Samaritan textual lineage of the Torah." },
      { name: "Codex Vaticanus", lang: "Greek Septuagint", date: "c. 4th c. AD", details: "One of the oldest surviving Christian codices of the Greek Old Testament." }
    ],
    interpretativeFrameworks: [
      {
        framework: "Western Historical-Critical",
        perspective: "Treats Moses as a foundational figure whose stories and laws were compiled and redacted during the Babylonian Exile (Documentary Hypothesis: JEDP sources)."
      },
      {
        framework: "East African Orthodox",
        perspective: "Emphasizes Moses' historic marriage to a Cushite (Ethiopian) woman (Numbers 12) as validating early covenantal ties and monotheistic lineages in East Africa."
      },
      {
        framework: "Decolonial Midrash",
        perspective: "Focuses on Moses as a political refugee of color who initiated an anti-imperial workers' strike against Pharaoh's dynasty, liberating marginalized slaves."
      }
    ],
    commentarySummaries: [
      "The Anchor Bible Commentary: Numbers 12:1 - The 'Cushite woman' Moses married is debated. Some identify her as Zipporah of Midian (Cush/Midian overlap), while others identify her as a secondary Ethiopian wife, highlighting ancient Near Eastern ties to East Africa.",
      "Logos Scholars Library: The law code of Moses at Sinai contains structural treaties resembling Hittite suzerainty covenants of the Late Bronze Age, reinforcing the antiquity of the text."
    ],
    mediaResources: [
      { title: "Exodus Route Reconstruction Map", type: "map", url: "map_exodus_route" },
      { title: "Before-and-After: Mount Sinai Archaeological Excavation", type: "image", url: "sinai_archeology" },
      { title: "The Sinai Covenant Treaty Structure Chart", type: "chart", url: "sinai_covenant_chart" }
    ],
    suggestedQuestions: [
      "Did Moses marry an Ethiopian woman?",
      "How does the covenant at Sinai compare with ancient Near Eastern treaties?",
      "Why was Moses forbidden from entering the Promised Land?"
    ]
  },
  "ethiopia": {
    slug: "ethiopia",
    name: "Ethiopia (Cush)",
    type: "place",
    summary: "Ethiopia, historically corresponding to the regions of Cush, Nubia, and Axum, plays a prominent and honorable role throughout biblical scripture. In the Table of Nations (Genesis 10), Cush is the eldest son of Ham. Throughout the Old Testament, Cushites appear as military allies, wealthy merchants, and worshipers of Yahweh (Psalm 68:31: 'Ethiopia shall stretch out her hands to God'). In the New Testament, the baptism of the Ethiopian Eunuch (Acts 8) represents the historical launch of African Christianity. The Ethiopian Orthodox Tewahedo Church preserves a unique canon including Enoch, Jubilees, and Meqabyan.",
    scriptureReferences: ["Genesis 2:13", "Genesis 10:6-8", "Numbers 12:1", "Psalm 68:31", "Isaiah 18:1-7", "Zephaniah 3:10", "Acts 8:26-40"],
    timelineEvents: [
      { year: "c. 2500 BC", event: "Kingdom of Cush emerges as a powerful Nile Valley civilization south of Egypt." },
      { year: "c. 715 BC", event: "25th Dynasty Cushite pharaohs (like Taharqa) rule over both Cush and Egypt." },
      { year: "c. 701 BC", event: "King Taharqa leads a Cushite army to relieve Jerusalem from Assyrian siege (2 Kings 19)." },
      { year: "c. 34 AD", event: "Philip baptizes the high treasurer of Queen Candace (Acts 8), carrying the Gospel to Axum." },
      { year: "c. 330 AD", event: "King Ezana declares Christianity as the state religion of the Axumite Empire." }
    ],
    geographicalMaps: [
      { name: "Axum (Ethiopia)", description: "The ancient capital of the Axumite Empire, home to the Church of Our Lady Mary of Zion.", lat: 14.129, lng: 38.718 },
      { name: "Meroë (Sudan/Cush)", description: "Capital of the Kingdom of Cush, famous for the Nubian pyramids and royal ironworks.", lat: 16.892, lng: 33.749 },
      { name: "Gihon River", description: "One of the four rivers of Eden, biblically associated with winding around the land of Cush.", lat: 12.0, lng: 37.0 }
    ],
    relatedPeople: ["Cush", "Taharqa (Tirhakah)", "Ebed-Melech", "Ethiopian Eunuch", "Frumentius", "Queen Candace"],
    relatedPlaces: ["Axum", "Meroë", "Nile River", "Sheba", "Jerusalem"],
    themes: ["Universal Gospel", "Royal Dignity", "Early African Christianity", "Decolonized Canon", "Decentralized Empires"],
    originalWords: [
      { word: "כּוּשׁ", lang: "Hebrew", strong: "H3568", def: "Kush - Refers to black-skinned descendants of Ham, Nubia, and southern lands." },
      { word: "Αἰθιοπία", lang: "Greek", strong: "G128", def: "Aithiopia - derived from 'burnt-face', denoting dark skin." },
      { word: "ኢትዮጵያ", lang: "Ge'ez", strong: "N/A", def: "Ityōṗṗyā - The Ge'ez term meaning Ethiopia." }
    ],
    manuscripts: [
      { name: "Garima Gospels", lang: "Ge'ez", date: "c. 5th c. AD", details: "One of the world's oldest illustrated Christian manuscripts, preserved in Axum." },
      { name: "Ezana Inscriptions", lang: "Ge'ez, Sabaean, Greek", date: "c. 330 AD", details: "Stone slab recording King Ezana's conversion to monotheistic Christianity." },
      { name: "Kebra Nagast Codices", lang: "Ge'ez", date: "c. 14th c. AD", details: "Epic chronicle outlining the Solomon-Sheba dynasty and translation of the Ark." }
    ],
    interpretativeFrameworks: [
      {
        framework: "Western Historical-Critical",
        perspective: "Often downplays 'Cush' as a peripheral geographical curiosity, translating it as 'Sudan' or 'Nubia' to separate it from Near Eastern narratives."
      },
      {
        framework: "East African Orthodox",
        perspective: "Views Cush/Ethiopia as a primary, chosen nation of scripture ('Ethiopia shall stretch out her hands to God'), retaining continuous monotheism since Solomon."
      },
      {
        framework: "Decolonial Midrash",
        perspective: "Recovers Ethiopia as the premier symbol of black presence, sovereignty, and wisdom in scripture, dismantling Eurocentric canonical selections."
      }
    ],
    commentarySummaries: [
      "Decolonized Biblical Studies: Modern western maps often replace 'Cush' with 'Nubia' or 'Sudan' to separate black African empires from the mainstream biblical narrative. Retaining the term Cush/Ethiopia connects East Africa directly to primary Near Eastern theology.",
      "Orthodox Tewahedo Scholars: Psalm 68:31 is considered a prophetic validation of Ethiopia's rapid adoption of Christian monotheism, bypassing western empires."
    ],
    mediaResources: [
      { title: "The Axumite Empire Map (4th Century CE)", type: "map", url: "axum_empire_map" },
      { title: "Archaeological Slider: Obelisks of Axum", type: "image", url: "axum_obelisk_slider" },
      { title: "Canon Structure: Broad vs Narrow", type: "chart", url: "canon_matrix" }
    ],
    suggestedQuestions: [
      "What is the biblical significance of Cush?",
      "How did the Ethiopian Eunuch launch Christianity in East Africa?",
      "Why is the Gihon river associated with Cush in Genesis 2?"
    ]
  },
  "jerusalem": {
    slug: "jerusalem",
    name: "Jerusalem",
    type: "place",
    summary: "Jerusalem is the spiritual and historical epicenter of the biblical narrative. Known originally as Salem (Melchizedek's kingdom) and Jebus, it was captured by King David around 1000 BC to become Israel's capital. Solomon built the Temple Mount there. The city was destroyed by Babylon in 586 BC, rebuilt under Ezra and Nehemiah, and later adorned by Herod. It is the site of Jesus' crucifixion, resurrection, and the birth of the early church at Pentecost. For centuries, it has been a place of theological convergence, debate, and prophecy.",
    scriptureReferences: ["Genesis 14:18", "2 Samuel 5:6-9", "Psalm 122:1-9", "Matthew 21:1-11", "Acts 1:4-8", "Revelation 21:1-4"],
    timelineEvents: [
      { year: "c. 2000 BC", event: "Melchizedek, king of Salem, blesses Abraham (Genesis 14)." },
      { year: "c. 1000 BC", event: "King David conquers Jerusalem from the Jebusites." },
      { year: "c. 957 BC", event: "Solomon completes construction of the First Temple." },
      { year: "586 BC", event: "Nebuchadnezzar destroys Jerusalem and the Temple, exiling Judeans." },
      { year: "c. 30 AD", event: "Jesus is crucified at Golgotha and rises from the tomb." }
    ],
    geographicalMaps: [
      { name: "Jerusalem (Old City)", description: "The ancient walled city containing Mount Zion and Golgotha.", lat: 31.778, lng: 35.235 },
      { name: "Temple Mount (Moriah)", description: "Site of Solomon's Temple, now home to the Dome of the Rock and Al-Aqsa.", lat: 31.778, lng: 35.236 },
      { name: "Mount of Olives", description: "Located east of Jerusalem, site of Jesus' ascension.", lat: 31.779, lng: 35.244 }
    ],
    relatedPeople: ["Melchizedek", "David", "Solomon", "Nehemiah", "Herod the Great", "Jesus Christ"],
    relatedPlaces: ["Salem", "Mount Zion", "Gethsemane", "Golgotha", "Valley of Hinnom"],
    themes: ["Sanctuary", "Exile and Return", "Atonement", "Messianic Reign", "Peace"],
    originalWords: [
      { word: "יְרוּשָׁלַם", lang: "Hebrew", strong: "H3389", def: "Yerushalaim - meaning 'foundation of peace' or 'double peace'." },
      { word: "Ἱεροσόλυμα", lang: "Greek", strong: "G2414", def: "Hierosolyma - Greek name for Jerusalem." },
      { word: "ኢየሩሳሌም", lang: "Ge'ez", strong: "N/A", def: "Iyerusalēm - The Ge'ez transliteration." }
    ],
    manuscripts: [
      { name: "Siloam Inscription", lang: "Paleo-Hebrew", date: "c. 8th c. BC", details: "Commemorates the construction of Hezekiah's tunnel beneath the City of David." },
      { name: "Temple Scroll (11Q19)", lang: "Hebrew", date: "c. 1st c. BC", details: "Dead Sea Scroll outline detailing the ideal dimensions and rituals for the Jerusalem Temple." },
      { name: "Madaba Mosaic Map", lang: "Greek", date: "c. 6th c. AD", details: "Oldest surviving cartographic depiction of Jerusalem and the Holy Land, found in Jordan." }
    ],
    interpretativeFrameworks: [
      {
        framework: "Western Historical-Critical",
        perspective: "Debates the archaeological scale of Jerusalem under David and Solomon, with minimalists arguing it was a small chiefdom village rather than an empire."
      },
      {
        framework: "East African Orthodox",
        perspective: "Jerusalem is the spiritual coordinate; the Ark's relocation to Axum establishes Ethiopia as the 'New Zion' and custodian of the original sanctuary."
      },
      {
        framework: "Decolonial Midrash",
        perspective: "Focuses on the city as a center of social stratification and prophetic protest, where prophets and Jesus confronted corrupt elites on behalf of the poor."
      }
    ],
    commentarySummaries: [
      "Critical Archaeology: Debates continue regarding the size of Jerusalem during David's reign. Minimalist scholars argue it was a small chiefdom village, while maximalist archaeologists point to the large stone structures in the City of David as evidence of a fortified royal capital.",
      "Theological Geography: Jerusalem's location in the Judean highlands placed it at the crossroads of major trade routes, making it a highly contested buffer state between Egypt and Assyria/Babylon."
    ],
    mediaResources: [
      { title: "Archaeological Slider: Jerusalem 3D Before-and-After (Jesus' Time vs Modern)", type: "image", url: "jerusalem_3d_slider" },
      { title: "Topographical Map of Ancient Jerusalem Valleys", type: "map", url: "jerusalem_valleys" }
    ],
    suggestedQuestions: [
      "What is the history of Salem before King David?",
      "Why did Jerusalem become the center of Israelite worship?",
      "What did archaeological excavations reveal about Nehemiah's walls?"
    ]
  },
  "covenant": {
    slug: "covenant",
    name: "Covenant",
    type: "doctrine",
    summary: "Covenant (Hebrew 'Berith', Greek 'Diatheke') is the central organizing concept of biblical theology. It denotes a solemn, binding relationship established by oath between God and humanity. The major covenants include the Cosmic Covenant (Noahic), the Promissory Covenant (Abrahamic), the Legal Covenant (Mosaic/Sinai), the Royal Covenant (Davidic), and the New Covenant prophesied by Jeremiah and enacted through Christ. Unlike modern contracts, covenants are relationship-defining alliances sealed with sacrifice, mutual oaths, and persistent signs (rainbow, circumcision, sabbath, communion).",
    scriptureReferences: ["Genesis 9:8-17", "Genesis 15:1-18", "Exodus 24:1-8", "2 Samuel 7:1-17", "Jeremiah 31:31-34", "Luke 22:20", "Hebrews 8:6-13"],
    timelineEvents: [
      { year: "Genesis 9", event: "Noahic Covenant: God promises never again to destroy the earth by flood." },
      { year: "Genesis 15/17", event: "Abrahamic Covenant: Promising land, offspring, and universal blessing." },
      { year: "Exodus 24", event: "Mosaic Covenant: Sinai law given with covenant ratification blood." },
      { year: "2 Samuel 7", event: "Davidic Covenant: An eternal throne promised to David's descendant." },
      { year: "Luke 22", event: "New Covenant: Inaugurated at the Last Supper with the blood of Christ." }
    ],
    geographicalMaps: [],
    relatedPeople: ["Noah", "Abraham", "Moses", "David", "Jeremiah", "Jesus Christ"],
    relatedPlaces: ["Mount Ararat", "Shechem", "Mount Sinai", "City of David", "Upper Room"],
    themes: ["Fidelity", "Oath", "Sacrifice", "Inheritance", "Redemption"],
    originalWords: [
      { word: "בְּרִית", lang: "Hebrew", strong: "H1285", def: "Berith - A covenant, treaty, or compact made by cutting (passing between split pieces)." },
      { word: "διαθήκη", lang: "Greek", strong: "G1242", def: "Diathekē - A testament, covenant, or unilateral disposition." },
      { word: "ኪዳን", lang: "Ge'ez", strong: "N/A", def: "Kīdān - Covenant, testament, or pact." }
    ],
    manuscripts: [
      { name: "Treaty of Kadesh Tablets", lang: "Akkadian / Egyptian", date: "c. 1258 BC", details: "World's oldest peace treaty; shows structural overlaps with Mosaic covenant formats." },
      { name: "Ketef Hinnom Silver Scrolls", lang: "Paleo-Hebrew", date: "c. 7th c. BC", details: "Tiny amulet scrolls containing the Priestly Blessing (Numbers 6), oldest surviving biblical text." },
      { name: "Qumran Community Rule (1QS)", lang: "Hebrew", date: "c. 1st c. BC", details: "Specifies the covenant renewal ceremonies and rules of the Essene community." }
    ],
    interpretativeFrameworks: [
      {
        framework: "Western Historical-Critical",
        perspective: "Analyses covenant structures as adaptations of Late Bronze Age Hittite and Assyrian suzerain-vassal treaties to secure national unity."
      },
      {
        framework: "East African Orthodox",
        perspective: "The 'Kidan' is a living, participatory contract (Kidanə Məḥrät - Covenant of Mercy) linking liturgy, families, and land in continuous sacred relationship."
      },
      {
        framework: "Decolonial Midrash",
        perspective: "Interprets covenant as a mutual agreement of social justice and shared resource stewardship, directly opposing imperial extraction economics."
      }
    ],
    commentarySummaries: [
      "Scholarly Consensus: Covenants are categorized as either 'conditional' (suzerain-vassal treaties where blessings depend on obedience, like Sinai) or 'unconditional' (royal grants where the suzerain binds himself eternally, like the Abrahamic and Davidic promises).",
      "Decolonizing Covenant: The Ethiopian Tewahedo Church identifies the 'Kidan' as an ongoing covenantal relationship between God, the Ark of the Covenant, and the Ethiopian people, emphasizing physical, continuous covenantal symbols."
    ],
    mediaResources: [
      { title: "Comparison Matrix of the 5 Major Biblical Covenants", type: "chart", url: "covenant_chart" }
    ],
    suggestedQuestions: [
      "What is the difference between a conditional and unconditional covenant?",
      "How did ancient Near Eastern covenants influence the covenant of Moses?",
      "What does 'cutting a covenant' mean in Hebrew culture?"
    ]
  },
  "enoch": {
    slug: "enoch",
    name: "Book of Enoch (1 Enoch)",
    type: "book",
    summary: "The Book of Enoch (specifically 1 Enoch) is an ancient Jewish apocryphal apocalyptic book attributed to Enoch, the great-grandfather of Noah. Written in Aramaic and Hebrew between the 3rd century BC and 1st century AD, it was widely read in early Judaism and early Christianity (quoted directly in Jude 14-15). While rejected by the Protestant, Catholic, and Rabbinic canons, it is fully canonical in the Ethiopian Orthodox Tewahedo Church, where the complete text survived solely in Ge'ez manuscripts. It describes the fall of the Watchers (Nephilim), Enoch's journeys through heaven, and the coming of the Son of Man.",
    scriptureReferences: ["Genesis 5:21-24", "Jude 1:14-15", "1 Peter 3:19-20", "2 Peter 2:4", "Hebrews 11:5"],
    timelineEvents: [
      { year: "c. 300 BC", event: "The Book of Watchers (1 Enoch 1-36) is composed." },
      { year: "c. 150 BC", event: "Aramaic fragments of Enoch are preserved in the Qumran caves (Dead Sea Scrolls)." },
      { year: "c. 90 AD", event: "Council of Jamnia and rabbinic authorities exclude Enoch from the Hebrew canon." },
      { year: "c. 382 AD", event: "Council of Rome and Jerome omit Enoch from the Latin Vulgate." },
      { year: "1773 AD", event: "Explorer James Bruce brings three Ge'ez manuscripts of 1 Enoch to Europe, revealing the complete text." }
    ],
    geographicalMaps: [
      { name: "Mount Hermon", description: "Where the Watchers descended to earth and swore oaths, according to Enoch 6.", lat: 33.416, lng: 35.856 },
      { name: "Qumran Caves", description: "Caves near the Dead Sea where Aramaic fragments of 1 Enoch were recovered.", lat: 31.741, lng: 35.459 }
    ],
    relatedPeople: ["Enoch", "Noah", "Methuselah", "Jared", "Jude", "James Bruce"],
    relatedPlaces: ["Mount Hermon", "Qumran", "Ethiopia", "Gondar"],
    themes: ["Apocalyptic Judgment", "The Watchers (Angels)", "Son of Man", "Cosmology", "Esotericism"],
    originalWords: [
      { word: "חֲנוֹך", lang: "Hebrew", strong: "H2585", def: "Chanokh - Dedicated or initiated." },
      { word: "Ἑνώχ", lang: "Greek", strong: "G1802", def: "Henōch - Transliteration of Enoch." },
      { word: "ሄኖክ", lang: "Ge'ez", strong: "N/A", def: "Hēnōk - The canonized title in Ge'ez." }
    ],
    manuscripts: [
      { name: "Aramaic Enoch Fragments (4Q201)", lang: "Aramaic", date: "c. 2nd c. BC", details: "Discovered in Qumran Caves, proving Enoch's pre-Christian Semitic origin." },
      { name: "Codex Panopolitanus", lang: "Greek", date: "c. 6th c. AD", details: "Christian grave scroll containing substantial Greek portions of the Book of Watchers." },
      { name: "Bruce Codex (Bodleian 506)", lang: "Ge'ez", date: "c. 18th c. AD", details: "Complete Ge'ez text brought to Europe by James Bruce, restoring 1 Enoch to Western scholarship." }
    ],
    interpretativeFrameworks: [
      {
        framework: "Western Historical-Critical",
        perspective: "Views Enoch as an apocryphal Jewish apocalypse composed in segments to cope with Hellenistic persecution under Antiochus Epiphanes."
      },
      {
        framework: "East African Orthodox",
        perspective: "Accepts Enoch as a fully canonical, inspired, antediluvian work written by the patriarch himself, preserved from the Flood in Ge'ez."
      },
      {
        framework: "Decolonial Midrash",
        perspective: "Interprets the fall of the Watchers (Enoch 6-10) as a radical political satire against military empires, colonial exploitation, and weapons manufacturing."
      }
    ],
    commentarySummaries: [
      "Dead Sea Scrolls Scholars: The discovery of Aramaic Enoch fragments at Qumran proved that 1 Enoch was not a post-Christian forgery, but a major Jewish sectarian text that influenced early Christian Christology and demonology.",
      "Ethiopian Orthodox Tewahedo Church: 1 Enoch is titled 'Mäṣḥafä Hēnōk'. Scholars view it as the oldest written book in human history, preserved by Noah through the flood and kept safe in Axum/Lasta."
    ],
    mediaResources: [
      { title: "1 Enoch Ge'ez Manuscript Page (18th Century)", type: "image", url: "enoch_manuscript" },
      { title: "Interactive Graph: Watchers and Angelic Hierarchy", type: "chart", url: "watchers_hierarchy" }
    ],
    suggestedQuestions: [
      "Why is 1 Enoch in the Ethiopian canon but not others?",
      "How did 1 Enoch influence the New Testament and the Book of Revelation?",
      "Who are the Watchers and what is Mount Hermon's connection?"
    ]
  }
};

// 2. Pre-audited Sermons for Analysis Simulator
export const MOCK_SERMON_ANALYSIS = {
  "accuracy_score": 78,
  "scripture_usage_score": 85,
  "context_score": 68,
  "theology_consistency_score": 82,
  "confidence_level": 94,
  "summary": {
    "topic": "The Location of Mount Sinai and the Route of the Exodus",
    "theme": "Geographic Exegesis and Historical Reliability",
    "short_summary": "This sermon argues that the traditional site of Mount Sinai in the Egyptian Sinai Peninsula is incorrect and suggests that the real Mount Sinai is Mount Jabal al-Lawz in modern-day Saudi Arabia (ancient Midian).",
    "detailed_summary": "The preacher outlines the route taken by Israel from Rameses, through Succoth and Etham, crossing the Red Sea (proposed at the Gulf of Aqaba rather than the Suez Canal), and arriving at Jabal al-Lawz in Midian. The speaker claims that Galatians 4:25 ('Mount Sinai in Arabia') geographically proves Sinai must be in modern Saudi Arabia, and that archaeological remains like chariot wheels on the sea floor confirm this crossing site.",
    "key_points": [
      "Traditional Sinai was selected by Constantine's mother, Helena, without biblical basis.",
      "Galatians 4:25 literally positions Mount Sinai in modern Saudi Arabia, outside Egyptian territory.",
      "The crossing took place at Nuweiba Beach across the Gulf of Aqaba.",
      "Jabal al-Lawz has a blackened peak, indicating the fire of Yahweh, and features a split rock matching Rephidim."
    ],
    "conclusion": "The sermon presents a compelling alternative narrative for the Exodus. However, it relies on controversial archaeological claims that are widely disputed by mainstream biblical geographers and historians."
  },
  "claims": [
    {
      "statement": "Constantine's mother, Helena, simply chose the traditional site of Mount Sinai in Egypt because she had a dream, with no biblical evidence.",
      "timestamp": "05:12",
      "severity": "partially_supported",
      "issue_type": "Historical Context Needed",
      "explanation": "While Helena did identify many holy sites in Palestine, the tradition identifying Jabal Musa in the southern Sinai Peninsula as Mount Sinai dates back to Jewish and early Christian hermits as early as the 2nd and 3rd centuries AD, long before Helena's pilgrimage in 326 AD.",
      "correction": "The southern Sinai tradition was already established by early monastic communities seeking solitude, not unilaterally invented by Helena.",
      "references": ["Egeria's Travels (381 AD)", "Eusebius of Caesarea (Onomasticon)"]
    },
    {
      "statement": "Galatians 4:25 says Mount Sinai is in Arabia, and since the Sinai Peninsula was in Egypt, Mount Sinai must be in modern Saudi Arabia.",
      "timestamp": "12:45",
      "severity": "debated",
      "issue_type": "Linguistic & Border Shift",
      "explanation": "In the Greco-Roman period (when Paul wrote Galatians), the Roman province of 'Arabia Petrea' encompassed the entire Sinai Peninsula, northwestern Arabia, and the Negev. Thus, 'Arabia' in Paul's day explicitly included the traditional Sinai Peninsula.",
      "correction": "Linguistically and politically, the Sinai Peninsula was considered part of Arabia during the 1st Century AD, so Paul's statement fits both the traditional and Saudi Arabian theories.",
      "references": ["Galatians 4:25", "Strabo (Geographica)", "Josephus (Antiquities)"]
    },
    {
      "statement": "Archaeologists found gold-plated Egyptian chariot wheels on the seafloor of the Gulf of Aqaba at Nuweiba Beach, proving the Red Sea crossing.",
      "timestamp": "18:30",
      "severity": "unsupported",
      "issue_type": "Unsupported Claim",
      "explanation": "This claim originated from amateur explorer Ron Wyatt in the late 1970s. Mainstream maritime archaeologists and academic institutions have surveyed the Gulf of Aqaba and found no verified Egyptian artifact remains. The claims were never published in peer-reviewed journals, and the 'gold wheels' are heavily deteriorated coral formations.",
      "correction": "There is currently no peer-reviewed archaeological evidence supporting the discovery of chariot wheels in the Gulf of Aqaba.",
      "references": ["Exodus 14:21-28", "Scholarly Review of Wyatt Archaeology (BAR Journal)"]
    },
    {
      "statement": "Jabal al-Lawz has a blackened basalt peak that stands out from the surrounding granite mountains, showing where God descended in fire.",
      "timestamp": "24:15",
      "severity": "debated",
      "issue_type": "Scientific Mismatch",
      "explanation": "Geological surveys of Jabal al-Lawz show that the dark peak is not blackened by fire or soot, but is actually composed of dark volcanic rocks (andesite and rhyolite) that predate the biblical Exodus by millions of years, overlaying the lighter granite base.",
      "correction": "The dark coloration of Jabal al-Lawz is a natural geological feature (metamorphic/volcanic rock), not the result of ancient heat or supernatural fire.",
      "references": ["Geological Survey of Saudi Arabia (1998)", "Exodus 19:18"]
    },
    {
      "statement": "Moses fled Egypt and lived in the land of Midian, which is historically located east of the Gulf of Aqaba in modern Saudi Arabia.",
      "timestamp": "29:05",
      "severity": "strongly_supported",
      "issue_type": "Supported Historical Geography",
      "explanation": "Biblical and external sources place the core territory of Midian in the northwestern Arabian Peninsula, east of the Gulf of Aqaba. Since Moses lived in Midian, and Sinai/Horeb was within shepherd grazing distance (Exodus 3:1), this constitutes a primary geographic pillar for the Saudi Arabian theory.",
      "correction": "Midian's historical core is indeed located in northwestern Arabia, supporting the idea that Mount Horeb was accessible from that region.",
      "references": ["Exodus 2:15", "Exodus 3:1", "Habakkuk 3:3"]
    }
  ],
  "transcript_segments": [
    { "timestamp": "00:00", "text": "Welcome brothers and sisters. Today we are digging deep into the historical reliability of the Exodus." },
    { "timestamp": "03:15", "text": "For generations, maps in the back of our Bibles have pointed to Jabal Musa in Egypt as Mount Sinai. But we must ask: where did this come from?" },
    { "timestamp": "05:12", "text": "Constantine's mother, Helena, simply chose the traditional site of Mount Sinai in Egypt because she had a dream, with no biblical evidence. She went there, pointed, and built a chapel." },
    { "timestamp": "09:40", "text": "But if we look at the Bible, Moses fled Pharaoh and went to Midian. Midian is not in the Sinai Peninsula. Midian is in Arabia." },
    { "timestamp": "12:45", "text": "Galatians 4:25 says Mount Sinai is in Arabia, and since the Sinai Peninsula was in Egypt, Mount Sinai must be in modern Saudi Arabia. It is Jabal al-Lawz." },
    { "timestamp": "16:20", "text": "And how did they cross? They crossed at Nuweiba Beach. There is a natural underwater land bridge across the Gulf of Aqaba." },
    { "timestamp": "18:30", "text": "Archaeologists found gold-plated Egyptian chariot wheels on the seafloor of the Gulf of Aqaba at Nuweiba Beach, proving the Red Sea crossing. These wheels remain there today as a monument of Yahweh's victory." },
    { "timestamp": "22:10", "text": "When you look at Jabal al-Lawz today, what do you see? It is a towering mountain in Saudi Arabia." },
    { "timestamp": "24:15", "text": "Jabal al-Lawz has a blackened basalt peak that stands out from the surrounding granite mountains, showing where God descended in fire. It is literally charred." },
    { "timestamp": "29:05", "text": "Remember, Moses fled Egypt and lived in the land of Midian, which is historically located east of the Gulf of Aqaba in modern Saudi Arabia. He kept Jethro's sheep and walked to the mountain. It fits perfectly." },
    { "timestamp": "34:00", "text": "Let us examine scripture and verify these things. Amen." }
  ],
  "further_study": [
    "The Exodus Route: Archaeological and Biblical Geography Studies, Hebrew University (2018)",
    "Paul's Geography in Galatians: Historical Mapping of Roman Arabia, Oxford Press (2012)",
    "Maritime Archaeological Surveys of the Gulf of Aqaba, Israel Antiquities Authority Reports",
    "Geology and Mineral Resources of the Northwestern Hijaz, Saudi Geological Survey Memoir"
  ],
  "processing_time": 3.4
};

// 3. Grounded answers library for Ask the Bible & Study Assistant
export const MOCK_ASK_ANSWERS = {
  "what does the bible say about forgiveness?": {
    answer: "Forgiveness in the biblical narrative is both a divine attribute and a core human obligation. In the Hebrew Bible, the primary term is **Salach** (סָלַח), which is used exclusively for God's forgiveness of humanity, and **Nasa** (נָשָׂא), meaning 'to lift up' or 'bear' iniquity. \n\nIn the New Testament, the Greek word is **Aphiemi** (ἀφίημι), which literally means 'to send away' or 'release' (as in canceling a debt). \n\n### Key Theological Themes\n1. **The Divine Paradigm**: God forgives human rebellion out of covenant fidelity, not human merit. This is demonstrated in the covenant renewal in Exodus 34:6-7.\n2. **Human Reciprocity**: Jesus emphasizes that receiving divine forgiveness is linked to forgiving others (Matthew 6:14-15, Matthew 18:21-35).\n3. **Decolonized Exegesis**: In traditional Western individualism, forgiveness is often reduced to a psychological release of anger. In ancient Near Eastern and African communal frameworks (such as the Ge'ez concept of **Səryät** ሥርየት), forgiveness is a restorational process that heals broken community relations, not just individual emotions.",
    sources: [
      {
        title: "Exodus 34:6-7",
        excerpt: "The Lord passed before him and proclaimed, 'The Lord, the Lord, a God merciful and gracious... forgiving iniquity and transgression and sin...'",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "Matthew 18:21-22",
        excerpt: "Then Peter came up and said to him, 'Lord, how often will my brother sin against me, and I forgive him? As many as seven times?' Jesus said to him, 'I do not say to you seven times, but seventy-seven times.'",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "Dictionary of Biblical Languages with Semantic Domains: Hebrew",
        excerpt: "סָלַח (salach): pardon, forgive, spare. Specifically used of God towards humans.",
        citation: "James Swanson, DBLH #6134",
        type: "original-language",
        confidenceScore: 0.95
      },
      {
        title: "African Biblical Hermeneutics Commentary",
        excerpt: "Forgiveness in Cushite traditions is communal (Ubuntu/Kidan), seeking restitution and restoring the offender to the tribal fellowship rather than merely releasing individual resentment.",
        citation: "Tewahedo Theological Review, Vol 14",
        type: "historical",
        confidenceScore: 0.88
      }
    ],
    followUps: [
      "What is the Ge'ez concept of Səryät?",
      "How does Jesus explain forgiveness in the parable of the unmerciful servant?",
      "What is the difference between Salach and Nasa in Hebrew?"
    ],
    confidenceRating: 98
  },
  "how does the ethiopian bible compare with the king james version on this passage?": {
    answer: "The **Ethiopian Orthodox Tewahedo Bible (81-book canon)** differs substantially from the **King James Version (66-book Protestant canon)** in breadth, ordering, and textual transmission. \n\n### Key Canon Differences\n* **The Protestant Canon (KJV)** contains 39 Old Testament books and 27 New Testament books. \n* **The Ethiopian Orthodox Canon** contains 46 Old Testament books (including 1 Enoch, Jubilees, Baruch, 1-3 Meqabyan, Tobit, Judith, and Sirach) and 35 New Testament books (including the Sinodos, Clement, Didaskalia, and the Book of the Covenant).\n\n### Textual Comparison on Key Passages\nFor instance, in **Genesis 6:1-4** (the account of the Sons of God and Daughters of Men), the KJV leaves the identity of the 'Sons of God' ambiguous, historically interpreted as Sethites. \n\nHowever, in **1 Enoch 6** (canonical only in Ethiopia), these figures are explicitly named as the **Watchers (Egigu)**, angelic beings who descended on Mount Hermon under the leadership of Semyaza, introducing metallurgy, sorcery, and cosmetics to humanity. This Enochic layer is essential to understanding the demonology of the New Testament (Jude 6, 2 Peter 2:4).",
    sources: [
      {
        title: "Jude 1:14-15",
        excerpt: "It was also about these that Enoch, the seventh from Adam, prophesied, saying, 'Behold, the Lord comes with ten thousands of his holy ones...'",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "The Ethiopian Orthodox Canon",
        excerpt: "The Tewahedo Church holds 81 books of Holy Scripture, divided into the Narrower Canon and the Broader Canon, preserving Enoch and Jubilees intact in Ge'ez.",
        citation: "Liturgy Department of the EOTC, Axum",
        type: "historical",
        confidenceScore: 0.96
      },
      {
        title: "Introduction to 1 Enoch",
        excerpt: "1 Enoch survived in its entirety only in the Ge'ez translation of the Axumite Empire, translated from Greek/Aramaic prototypes in the 5th century CE.",
        citation: "Ephraim Isaac, The Enoch Seminar",
        type: "historical",
        confidenceScore: 0.94
      }
    ],
    followUps: [
      "Who are the Watchers in the Book of Enoch?",
      "What are the books of Meqabyan?",
      "How did James Bruce recover the Ge'ez Enoch manuscripts?"
    ],
    confidenceRating: 95
  },
  "what is the historical background of this chapter?": {
    answer: "The historical context of biblical chapters varies depending on their composition date and sociological setting. For **Genesis 1-11**, the texts emerged in dialogue with ancient Near Eastern creation and flood epics, such as the Babylonian **Enuma Elish** and the **Epic of Gilgamesh**. \n\nRather than copying these texts, the biblical writers engaged in **theological subversion**: \n* While Babylonian epics depict creation as the result of violent wars among capricious deities, Genesis depicts creation through the effortless, ordered speech of a transcendent God.\n* While Gilgamesh depicts the gods wiping out humanity because they were too noisy, Genesis depicts the flood as a moral response to systemic human violence (**Chamas**).\n\nFor **Exodus**, the background is the Late Bronze Age Egypt (15th-13th Century BC) under New Kingdom pharaohs (likely Amenhotep II or Ramesses II), a period characterized by major state construction projects employing slave labor.",
    sources: [
      {
        title: "Genesis 1:1-2",
        excerpt: "In the beginning, God created the heavens and the earth. The earth was without form and void, and darkness was over the face of the deep...",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "Ancient Near Eastern Texts Relating to the Old Testament",
        excerpt: "Comparative analysis of Enuma Elish and Genesis creation narratives highlights structural parallels (creation of light, expanse, dry land, luminaries, humanity) alongside stark monotheistic divergences.",
        citation: "James B. Pritchard, ANET",
        type: "historical",
        confidenceScore: 0.93
      },
      {
        title: "The Pentateuch in Historical Context",
        excerpt: "Exodus reflects the administrative and geographical realities of the Ramesside period in the eastern Nile delta.",
        citation: "Kenneth Kitchen, On the Reliability of the Old Testament",
        type: "historical",
        confidenceScore: 0.89
      }
    ],
    followUps: [
      "How does the flood in Genesis compare to the Epic of Gilgamesh?",
      "Which Pharaoh is historically linked to the Exodus?",
      "What is the theological subversion in the Tower of Babel narrative?"
    ],
    confidenceRating: 92
  },
  "what are the major cross-references for this theme?": {
    answer: "Understanding scripture through scripture is a primary scholarly methodology. If we trace the theme of the **Son of Man (Bar Enash)**, we see a rich web of intertextuality:\n\n1. **Daniel 7:13-14**: The primary seed text, where one 'like a Son of Man' rides on the clouds of heaven, is presented before the Ancient of Days, and receives an everlasting, universal kingdom.\n2. **1 Enoch 46:1-3 & 48:2**: The Similitudes of Enoch expand this figure into a pre-existent messianic judge who sits on the throne of glory, crushes the kings of the earth, and serves as a light to the Gentiles.\n3. **Matthew 26:63-64**: Jesus directly fuses these texts when confronted by the High Priest. He asserts: 'You will see the Son of Man seated at the right hand of Power and coming on the clouds of heaven.' This explains why the Sanhedrin immediately charged him with blasphemy—they recognized he was claiming the divine-messianic status of Daniel and Enoch's Son of Man.",
    sources: [
      {
        title: "Daniel 7:13",
        excerpt: "I saw in the night visions, and behold, with the clouds of heaven there came one like a son of man, and he came to the Ancient of Days...",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "1 Enoch 46:3",
        excerpt: "And he answered and said to me: 'This is the Son of Man who has righteousness, with whom dwelling-place is righteousness...'",
        citation: "R.H. Charles, Translation of 1 Enoch",
        type: "scripture",
        confidenceScore: 0.97
      },
      {
        title: "Matthew 26:64",
        excerpt: "Jesus said to him, 'You have said so. But I tell you, from now on you will see the Son of Man seated at the right hand of Power and coming on the clouds of heaven.'",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      }
    ],
    followUps: [
      "What does the title 'Son of Man' mean in Hebrew/Aramaic?",
      "How does Jesus use this title in the Gospels?",
      "What is the relation between Daniel 7 and the Book of Revelation?"
    ],
    confidenceRating: 97
  },
  "what does the original hebrew, greek, aramaic, or geʽez suggest?": {
    answer: "Original language study reveals deep nuances that translations inevitably obscure. Let us examine the Hebrew word **Almah** (עַלְמָה) in **Isaiah 7:14** ('Behold, the almah shall conceive and bear a son').\n\n* **Hebrew (Almah)**: Refers to a young woman of childbearing age, who is presumably a virgin, but the word itself doesn't explicitly guarantee virginity (for which **Betulah** is the specific legal term).\n* **Greek Septuagint (Parthenos - παρθένος)**: Translated in Egypt around 250 BC, the Jewish translators rendered *almah* as *parthenos*, which explicitly means 'virgin'. This shows that 250 years before Jesus, Alexandria's Jewish scholars understood the prophecy to foretell a miraculous virgin birth.\n* **Ge'ez (Dəngəl - ድንግል)**: Translating the Greek Septuagint, the Ge'ez Bible uses *Dəngəl*, signifying absolute virginity, which matches the Ethiopian Orthodox Mariological and Christological emphasis.",
    sources: [
      {
        title: "Isaiah 7:14",
        excerpt: "Therefore the Lord himself will give you a sign. Behold, the virgin [almah] shall conceive and bear a son, and shall call his name Immanuel.",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "Hebrew and Aramaic Lexicon of the Old Testament",
        excerpt: "עַלְמָה (almah): young woman (marriageable age, until the birth of her first child), virgin.",
        citation: "Koehler and Baumgartner, HALOT #6574",
        type: "original-language",
        confidenceScore: 0.96
      },
      {
        title: "Gesenius' Hebrew Grammar",
        excerpt: "Almah indicates youth and sexual maturity, without legal statement of virginity, unlike Betulah, which specifies virginity but can occasionally apply to a betrothed young widow.",
        citation: "Gesenius, Section 122",
        type: "original-language",
        confidenceScore: 0.94
      }
    ],
    followUps: [
      "How is Greek Parthenos used in Matthew 1:23?",
      "What are other instances of the word Almah in the Old Testament?",
      "What is the difference between Betulah and Almah?"
    ],
    confidenceRating: 94
  },
  "how would i explain this passage to a teenager?": {
    answer: "Let's take **Genesis 3** (the serpent and the forbidden fruit) and explain it in a way that resonates with a teenager today:\n\n### The Setup\nThink of the Garden of Eden like a perfect sandbox, the ultimate setup where humans had total freedom, healthy relationships, and direct connection with God. God gave them one rule: don't eat from the Tree of Knowledge of Good and Evil. This wasn't about trying to ruin their fun; it was about trust. It was God saying, 'Let me define what is good for you and what is bad. Trust my judgment.'\n\n### The Glitch (The Temptation)\nThe serpent enters. He doesn't look like a cartoon monster. Instead, he whispers: *'Did God really say that? Is he holding out on you? If you eat it, you'll be like God, making your own rules.'* This is the original peer pressure, the fear of FOMO (Fear Of Missing Out). The serpent convinces Adam and Eve that God is holding them back and that they should decide right and wrong for themselves.\n\n### The Crash (The Fallout)\nThey eat the fruit. Immediately, the vibe changes. Instead of feeling like gods, they feel exposed, ashamed, and disconnected. They hide from God and start pointing fingers—Adam blames Eve, Eve blames the snake. This is exactly what happens when we break trust today: we hide, we feel insecure, and we blame others. The story shows that sin isn't just about breaking arbitrary rules; it's about breaking relationships and trying to run the show ourselves, which always leads to a crash.",
    sources: [
      {
        title: "Genesis 3:6",
        excerpt: "So when the woman saw that the tree was good for food, and that it was a delight to the eyes... she took of its fruit and ate...",
        citation: "Scripture Standard Version (SSV)",
        type: "scripture",
        confidenceScore: 0.99
      },
      {
        title: "Youth Discipleship Handbook",
        excerpt: "Translating ancient ancient Near Eastern symbols (fruit, serpent, garden) into modern teenage concepts of trust, autonomy, shame, and blame increases scriptural comprehension.",
        citation: "Teen Faith Publishing, 2021",
        type: "historical",
        confidenceScore: 0.85
      }
    ],
    followUps: [
      "What is the spiritual meaning of the fig leaves?",
      "Why did God ask 'Where are you?' if he already knew?",
      "How does Jesus fix the crash of Genesis 3?"
    ],
    confidenceRating: 90
  }
};

// 4. Interactive Media Data Structures
export const MOCK_BIBLE_BOOKS = [
  { id: "torah", name: "Pentateuch / Torah", color: "#FF6B35", books: ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"], genre: "Law & Origins" },
  { id: "history", name: "Historical Books", color: "#F7931E", books: ["Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther"], genre: "National History" },
  { id: "poetry", name: "Poetry & Wisdom", color: "#FFD23F", books: ["Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Sirach", "Wisdom"], genre: "Wisdom Lit" },
  { id: "prophets", name: "Prophetic Books", color: "#06FFA5", books: ["Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi", "Enoch", "Jubilees"], genre: "Prophecy & Apocalypse" },
  { id: "gospels", name: "Gospels & Acts", color: "#3B82F6", books: ["Matthew", "Mark", "Luke", "John", "Acts"], genre: "Life of Christ & Early Church" },
  { id: "epistles", name: "Epistles", color: "#8B5CF6", books: ["Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude"], genre: "Letters to Churches" },
  { id: "apocalypse", name: "Apocalypse", color: "#EF4444", books: ["Revelation"], genre: "Revelation" }
];

export const MOCK_PSALMS_CATEGORIES = [
  { category: "Lament", description: "Crying out to God in times of crisis, pain, or persecution.", examples: ["Psalm 3", "Psalm 13", "Psalm 22", "Psalm 51", "Psalm 88"], percent: 40 },
  { category: "Praise / Hymns", description: "Adoring God for who He is, His majesty, and His creation.", examples: ["Psalm 8", "Psalm 19", "Psalm 103", "Psalm 104", "Psalm 150"], percent: 25 },
  { category: "Thanksgiving", description: "Giving thanks for specific acts of deliverance or answered prayer.", examples: ["Psalm 30", "Psalm 34", "Psalm 116", "Psalm 118"], percent: 15 },
  { category: "Wisdom & Torah", description: "Reflecting on the law of God, righteous living, and two paths.", examples: ["Psalm 1", "Psalm 19:7-14", "Psalm 119"], percent: 10 },
  { category: "Royal & Messianic", description: "Focusing on the king of Israel and the ultimate anointed one.", examples: ["Psalm 2", "Psalm 45", "Psalm 72", "Psalm 110"], percent: 10 }
];

export const MOCK_TIMELINE_EVENTS = [
  { epoch: "Patriarchal Era", date: "c. 2100 BC", title: "Covenant with Abraham", desc: "Abraham leaves Ur and goes to Canaan; God covenants to bless all nations through him." },
  { epoch: "Exodus Period", date: "c. 1446 BC", title: "Exodus & Mount Sinai", desc: "Moses leads Israel out of Egyptian slavery, receiving the Ten Commandments at Sinai." },
  { epoch: "United Kingdom", date: "c. 1000 BC", title: "David's Jerusalem Capital", desc: "David captures Jebus, establishes Jerusalem as the royal political and spiritual capital." },
  { epoch: "Divided Kingdom", date: "c. 722 BC", title: "Fall of Samaria", desc: "Assyrian Empire destroys the Northern Kingdom of Israel, deporting its tribes." },
  { epoch: "Babylonian Exile", date: "c. 586 BC", title: "Destruction of Jerusalem", desc: "Nebuchadnezzar burns Solomon's Temple; Judah is exiled to Babylon." },
  { epoch: "Post-Exile", date: "c. 516 BC", title: "Second Temple Completed", desc: "Zerubbabel completes rebuilding the Temple; Ezra and Nehemiah restore walls and Torah." },
  { epoch: "Time of Jesus", date: "c. 30 AD", title: "Crucifixion & Resurrection", desc: "Jesus of Nazareth is executed under Pontius Pilate and rises, founding the Christian faith." },
  { epoch: "Apostolic Era", date: "c. 50-95 AD", title: "Writing of the New Testament", desc: "Paul, Peter, John, and others compose letters and gospels, spreading the Church." }
];

export const MOCK_ARCHAEOLOGICAL_SLIDES = [
  {
    id: "temple_mount",
    title: "The Second Temple / Herod's Temple (Jerusalem)",
    beforeDesc: "Artist reconstruction of the temple complex in 30 AD, showcasing the majestic white marble sanctuary, royal stoa, and detailed colonnades.",
    afterDesc: "Modern photograph of the Temple Mount, featuring the golden Dome of the Rock, Al-Aqsa Mosque, and the surrounding ancient stone walls.",
    beforeImg: "/assets/temple_mount_before.png",
    afterImg: "/assets/temple_mount_after.png"
  },
  {
    id: "babylon_gate",
    title: "The Ishtar Gate (Babylon)",
    beforeDesc: "Reconstruction of the grand glazed blue brick gate of King Nebuchadnezzar II, guarding the processional way into Babylon with reliefs of dragons and bulls.",
    afterDesc: "The excavated archaeological ruins of Babylon in modern-day Iraq, showing the mudbrick gate foundations and processional excavation layers.",
    beforeImg: "/assets/ishtar_gate_before.png",
    afterImg: "/assets/ishtar_gate_after.png"
  }
];

export const MOCK_CANON_MATRIX = [
  { book: "Genesis", prot: true, cath: true, orth: true, eth: true },
  { book: "Tobit", prot: false, cath: true, orth: true, eth: true },
  { book: "Judith", prot: false, cath: true, orth: true, eth: true },
  { book: "1 Maccabees", prot: false, cath: true, orth: true, eth: true },
  { book: "1 Meqabyan (Eth. Maccabees)", prot: false, cath: false, orth: false, eth: true },
  { book: "2 Meqabyan", prot: false, cath: false, orth: false, eth: true },
  { book: "3 Meqabyan", prot: false, cath: false, orth: false, eth: true },
  { book: "Book of Enoch (1 Enoch)", prot: false, cath: false, orth: false, eth: true },
  { book: "Book of Jubilees", prot: false, cath: false, orth: false, eth: true },
  { book: "Wisdom of Solomon", prot: false, cath: true, orth: true, eth: true },
  { book: "Baruch", prot: false, cath: true, orth: true, eth: true },
  { book: "Matthew", prot: true, cath: true, orth: true, eth: true },
  { book: "Romans", prot: true, cath: true, orth: true, eth: true },
  { book: "Didaskalia (Ethiopian)", prot: false, cath: false, orth: false, eth: true },
  { book: "Sinodos (Ethiopian)", prot: false, cath: false, orth: false, eth: true }
];
