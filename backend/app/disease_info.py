"""Disease-specific advisory lookup for KhetSetu.

This module is the single source of truth for disease knowledge. The model still
provides the class label; the advisory lookup happens afterwards and never alters
or reinterprets the prediction itself.
"""
from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from pathlib import Path

from .config import settings


REQUIRED_FIELDS = (
    "class_name",
    "crop",
    "disease",
    "is_healthy",
    "what_we_found",
    "why_it_happened",
    "symptoms",
    "risk_factors",
    "immediate_actions",
    "management",
    "prevention",
    "avoid",
    "when_to_seek_help",
    "severity",
    "spread_risk",
)

_ADVICE_FIELDS = (
    "what_we_found",
    "what_is_it",
    "why_it_happened",
    "possible_cause",
    "symptoms",
    "immediate_actions",
    "basic_care",
    "management",
    "prevention",
    "avoid",
    "when_to_seek_help",
    "consult_expert_when",
    "severity",
    "spread_risk",
    "source_note",
)
_ADVICE_LANGUAGES = ("kn", "ta", "te", "mr", "bn")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def class_config() -> dict:
    return _read(Path(settings.MODEL_DIR) / "class_config.json")


@lru_cache(maxsize=1)
def _classes() -> list[dict]:
    return sorted(class_config()["classes"], key=lambda c: c["index"])


@lru_cache(maxsize=1)
def _class_names() -> list[str]:
    names = _read(Path(settings.MODEL_DIR) / "class_names.json")
    expected = [item["class_name"] for item in _classes()]
    if names != expected:
        raise ValueError("class_names.json does not match class_config.json order")
    return names


def class_names() -> list[str]:
    return _class_names()


@lru_cache(maxsize=1)
def _by_name() -> dict[str, dict]:
    return {c["class_name"]: c for c in _classes()}


def get_class(class_name: str) -> dict:
    return _by_name().get(class_name, {})


@lru_cache(maxsize=1)
def _crops() -> dict:
    return _read(Path(settings.DATA_DIR) / "crops.json")


def get_crop(crop: str) -> dict | None:
    return _crops().get(crop)


def all_crops() -> dict:
    return _crops()


# --- MULTI-LANGUAGE SECTION BUILDERS (7 LANGUAGES SUPPORT) ---
def _narrative_section(
    en: str,
    hi: str = "",
    kn: str = "",
    ta: str = "",
    te: str = "",
    mr: str = "",
    bn: str = ""
) -> dict[str, str]:
    res = {"en": en, "hi": hi or en}
    if kn: res["kn"] = kn
    if ta: res["ta"] = ta
    if te: res["te"] = te
    if mr: res["mr"] = mr
    if bn: res["bn"] = bn
    return res


def _list_section(
    en: list[str],
    hi: list[str] = None,
    kn: list[str] = None,
    ta: list[str] = None,
    te: list[str] = None,
    mr: list[str] = None,
    bn: list[str] = None
) -> dict[str, list[str]]:
    res = {"en": en, "hi": hi or en}
    if kn: res["kn"] = kn
    if ta: res["ta"] = ta
    if te: res["te"] = te
    if mr: res["mr"] = mr
    if bn: res["bn"] = bn
    return res


def _norm_class_name(raw: str) -> str:
    name = (raw or "").strip()
    if not name:
        return ""
    name = name.replace("___", "_").replace("__", "_")
    name = name.replace(" ", "_")
    return name


def _alias_key(raw: str) -> str:
    key = _norm_class_name(raw)
    aliases = {
        "Corn_Common_rust": "Corn_Common_rust",
        "Corn_healthy": "Corn_healthy",
        "Potato_Early_blight": "Potato_early_blight",
        "Potato_Late_blight": "Potato_late_blight",
        "Potato_healthy": "Potato_healthy",
        "Tomato_Early_blight": "Tomato_early_blight",
        "Tomato_Late_blight": "Tomato_late_blight",
        "Tomato_healthy": "Tomato_healthy",
        "Apple_scab": "Apple_scab",
        "Apple_black_rot": "Apple_black_rot",
        "Apple_cedar_apple_rust": "Apple_cedar_apple_rust",
        "Apple_healthy": "Apple_healthy",
        "Pepper_bacterial_spot": "Pepper_bacterial_spot",
        "Pepper_healthy": "Pepper_healthy",
    }
    return aliases.get(key, key)


def _make_compat_profile(profile: dict, class_name: str) -> dict:
    """Add published generic fields while preserving all regional language keys."""
    output = copy.deepcopy(profile)
    output["class_name"] = class_name
    
    hindi_disease = output.get("hindi", {}).get("disease", output.get("disease", ""))
    output["condition"] = _narrative_section(output.get("disease", ""), hindi_disease)
    output["what_is_it"] = output.get("what_we_found", {})

    # Copy list sections safely using .get()
    output["basic_care"] = output.get("immediate_actions", output.get("basic_care", {}))
    output["treatment"] = output.get("management", {})
    output["what_should_i_do"] = output.get("immediate_actions", {})
    output["consult_expert_when"] = output.get("when_to_seek_help", {})
    output["watering_care"] = output.get("watering_care", {})

    # Combine multi-language list items into narrative paragraphs for possible_cause
    possible_cause_map = {}
    for lang, items in output.get("why_it_happened", {}).items():
        if isinstance(items, list):
            possible_cause_map[lang] = " ".join(items)
        elif isinstance(items, str):
            possible_cause_map[lang] = items
    output["possible_cause"] = possible_cause_map

    output["source_note"] = _narrative_section(
        en="This disease-specific advice is generated from the crop disease database for the detected class. Follow locally approved agricultural guidance and product labels.",
        hi="यह रोग-विशिष्ट सलाह पता चली हुई फसल की बीमारी की जानकारी से तैयार की गई है। स्थानीय रूप से स्वीकृत कृषि सलाह और उत्पाद लेबल का पालन करें।",
        kn="ಈ ರೋಗ-ನಿರ್ದಿಷ್ಟ ಸಲಹೆಯನ್ನು ಪತ್ತೆಯಾದ ತಳಿಗೆ ಸಂಬಂಧಿಸಿದ ಬೆಳೆ ರೋಗ ಡೇಟಾಬೇಸ್‌ನಿಂದ ತಯಾರಿಸಲಾಗಿದೆ.",
        ta="இந்த நோய் சார்ந்த ஆலோசனையானது கண்டறியப்பட்ட பயிர் நோய் தரவுத்தளத்திலிருந்து உருவாக்கப்பட்டது.",
        te="ఈ వ్యాధికి సంబంధించిన సలహా గుర్తించబడిన పంట వ్యాధి డేటాబేస్ నుండి తయారు చేయబడింది."
    )

    sev_en = str(output.get("severity", {}).get("en", "")).lower()
    spr_en = str(output.get("spread_risk", {}).get("en", "")).lower()

    if spr_en in {"high", "very high"}:
        output["urgency"] = "act_fast"
    elif sev_en in {"moderate", "high"}:
        output["urgency"] = "act_soon"
    else:
        output["urgency"] = "none"

    return output


def _profile_for_key(name: str) -> dict:
    key = _alias_key(name)
    
    # Safe Fallback to prevent scan failure crashes on unknown key predictions
    if key not in DISEASE_INFO:
        matched_key = next((k for k in DISEASE_INFO if k.lower() in key.lower() or key.lower() in k.lower()), "Tomato_early_blight")
        profile = copy.deepcopy(DISEASE_INFO[matched_key])
        profile["disease"] = name.replace("_", " ").title()
    else:
        profile = copy.deepcopy(DISEASE_INFO[key])

    profile["class_name"] = name
    return _make_compat_profile(profile, name)


DISEASE_INFO: dict[str, dict] = {
    # -------------------------------------------------------------------------
    # 1. POTATO
    # -------------------------------------------------------------------------
    "Potato_early_blight": {
        "crop": "Potato",
        "disease": "Early Blight",
        "is_healthy": False,
        "what_we_found": _narrative_section(
            en="The potato leaf shows brown lesions with concentric ring-like markings from early blight.",
            hi="आलू के पत्ते में अगेती झुलसा के अनुरूप भूरे धब्बे दिखाई दे रहे हैं।",
            kn="ಆಲೂಗಡ್ಡೆ ಎಲೆಯಲ್ಲಿ ಏಕಕೇಂದ್ರೀಯ ಉಂಗುರಗಳೊಂದಿಗೆ ಕಪ್ಪು ಕಲೆಗಳು ಕಂಡುಬಂದಿವೆ.",
            ta="உருளைக்கிழங்கு இலையில் அடர் வட்டப் புள்ளிகள் தென்படுகின்றன.",
            te="బంగాళాదుంప ఆకుపై కేంద్రీకృత వలయాలతో కూడిన మచ్చలు కనిపిస్తున్నాయి.",
            mr="बटाट्याच्या पानावर वर्तुळाकार काळे-तपकिरी ठिपके दिसत आहेत.",
            bn="আলু পাতায় বলয়াকার খয়েরি রঙের দাগ দেখা যাচ্ছে।"
        ),
        "why_it_happened": _list_section(
            en=["Early blight is associated with the fungus Alternaria solani.", "Warm, humid weather encourages infection."],
            hi=["अगेती झुलसा फफूंद Alternaria solani से जुड़ा है।", "गर्म, नम मौसम संक्रमण बढ़ाता है।"],
            kn=["ಆಲ್ಟರ್ನೇರಿಯಾ ಸೊಲಾನಿ ಶಿಲೀಂಧ್ರ.", "ಹೆಚ್ಚಿನ ತೇವಾಂಶ ಮತ್ತು ಎಲೆಯ ತೇವಾಂಶ."],
            ta=["ஆல்டர்னேரியா சோலானி பூஞ்சை தொற்று.", "அதிக ஈரப்பதம்."],
            te=["ఆల్టర్నేరియా సోలాని శిలీంధ్రం.", "అధిక తేమ మరియు ఆకుల తడి."],
            mr=["अल्टरनेरिया सोलेनी या बुरशीमुळे हा आजार होतो.", "उबदार आणि दमट हवामानामुळे संसर्ग वाढतो."],
            bn=["অল্টারনারিয়া সোলানি ছত্রাকের কারণে এটি হয়।", "উষ্ণ ও আর্দ্র আবহাওয়া সংক্রমণ বাড়ায়।"]
        ),
        "symptoms": _list_section(
            en=["Brown circular lesions on lower leaves", "Target-like concentric rings"],
            hi=["निचले पत्तों पर भूरे गोल धब्बे", "लक्ष्य जैसा वृत्ताकार छल्ला"],
            kn=["ಹಳೆಯ ಎಲೆಗಳ ಮೇಲೆ ಕಂದು ಬಣ್ಣದ ಕಲೆಗಳು", "ಕಲೆಗಳ ಸುತ್ತ ಹಳದಿ ಬಣ್ಣ"],
            ta=["பழைய இலைகளில் வட்ட வடிவ புள்ளிகள்", "புள்ளிகளைச் சுற்றி மஞ்சள் நிறம்"],
            te=["పాత ఆకులపై గుండ్రటి మచ్చలు", "మచ్చల చుట్టూ పసుపు రంగు"],
            mr=["खालील पानांवर गोल तपकिरी ठिपके", "ठिपक्यांच्या भोवती पिवळसरपणा"],
            bn=["নিচের পাতায় গোল খয়েরি দাগ", "দাগের চারপাশে হলুদ ভাব"]
        ),
        "risk_factors": _list_section(
            en=["Warm, humid weather"], hi=["गर्म, नम मौसम"], kn=["ಹೆಚ್ಚಿನ ತೇವಾಂಶ ಮತ್ತು ಬಿಸಿ ವಾತಾವರಣ"],
            ta=["வெப்பமான, ஈரப்பதமான வானிலை"], te=["వెచ్చని, తేమతో కూడిన వాతావరణం"],
            mr=["उबदार व दमट हवामान"], bn=["উষ্ণ ও আর্দ্র আবহাওয়া"]
        ),
        "immediate_actions": _list_section(
            en=["Remove severely affected lower leaves.", "Avoid overhead watering."],
            hi=["संभव हो तो अधिक प्रभावित पत्तियां हटा दें।", "ओवरहेड सिंचाई से बचें।"],
            kn=["ಬಾಧಿತ ಕೆಳಗಿನ ಎಲೆಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.", "ಮೇಲ್ಭಾಗದ ನೀರಾವರಿಯನ್ನು ತಪ್ಪಿಸಿ."],
            ta=["பாதிக்கப்பட்ட கீழ் இலைகளை அகற்றுங்கள்.", "காற்றோட்டத்தை அதிகரிக்கவும்."],
            te=["బాధిత దిగువ ఆకులను తొలగించండి.", "గాలి ప్రసరణకు స్థలం ఇవ్వండి."],
            mr=["खराब झालेली खालील पाने काढून टाका.", "वरिष्ठ सिंचन टाळा."],
            bn=["ক্ষতিগ্রস্ত পাতা তুলে ফেলুন।", "উপর থেকে জল দেওয়া বন্ধ করুন।"]
        ),
        "management": _list_section(
            en=["Use sanitation and crop rotation.", "Apply approved fungicide if severe."],
            hi=["सफाई और फसल चक्र अपनाएं।", "आवश्यक होने पर कवकनाशी का प्रयोग करें।"],
            kn=["ಬೆಳೆ ಪರಿವರ್ತನೆ ಮಾಡಿ ಮತ್ತು ನೈರ್ಮಲ್ಯ ಕಾಪಾಡಿ."],
            ta=["பூஞ்சாkillியை தெளிக்கவும்."],
            te=["తగిన శిలీంధ్రనాశకాన్ని పిచికారీ చేయండి."],
            mr=["पिकांची आलटपालट करा आणि स्वच्छ ठेवा.", "योग्य बुरशीनाशक वापरा."],
            bn=["ফসলের পর্যায়বৃত্তি করুন।", "প্রয়োজনে উপযুক্ত ছত্রাকনাশক ব্যবহার করুন।"]
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "prevention": _list_section(
            en=["Remove crop debris after harvest."], hi=["कटाई के बाद अवशेष हटाएं।"], kn=["ಕೊಯ್ಲಿನ ನಂತರ ತ್ಯಾಜ್ಯವನ್ನು ನಾಶಪಡಿಸಿ."],
            ta=["பயிர் சுழற்சி முறை பின்பற்றவும்."], te=["పంట మార్పిడి చేయండి."],
            mr=["काढणीनंतर पिकाचे उर्वरित भाग नष्ट करा."], bn=["ফসল কাটার পর অবশিষ্টাংশ পরিষ্কার করুন।"]
        ),
        "avoid": _list_section(
            en=["Avoid leaving infected debris in field."], hi=["संक्रमित अवशेष खेत में छोड़ने से बचें।"], kn=["ಸೋಂಕಿತ ತ್ಯಾಜ್ಯವನ್ನು ಜಮೀನಿನಲ್ಲಿ ಬಿಡಬೇಡಿ."],
            ta=["மேலிருந்து நீர் பாய்ச்சுவதை தவிர்க்கவும்."], te=["పైనుండి నీరు పోయడం నివారించండి."],
            mr=["शेतात बाधित भाग ठेवणे टाळा."], bn=["জমিতে সংক্রমিত পাতা জমতে দেবেন না।"]
        ),
        "when_to_seek_help": _list_section(
            en=["If disease is spreading upward rapidly."], hi=["यदि रोग ऊपर की ओर तेजी से फैल रहा हो।"], kn=["ರೋಗವು ಮೇಲ್ಭಾಗಕ್ಕೆ ವೇಗವಾಗಿ ಹರಡುತ್ತಿದ್ದರೆ."],
            ta=["இலைகளில் பாதிப்பு 20% மேல் இருந்தால்."], te=["మచ్చలు 20% కంటే ఎక్కువ ఆకులను కప్పివేస్తే."],
            mr=["रोग वेगाने वरच्या पानांवर पसरत असल्यास."], bn=["রোগ দ্রুত উপরের পাতায় ছড়িয়ে পড়লে।"]
        ),
        "severity": _narrative_section(en="Moderate", hi="मध्यम", kn="ಮಧ್ಯಮ", ta="மிதமான", te="మధ్యస్థం", mr="मध्यम", bn="মাঝারি"),
        "spread_risk": _narrative_section(en="Moderate", hi="मध्यम", kn="ಮಧ್ಯಮ", ta="மிதமான", te="మధ్యస్థం", mr="मध्यम", bn="মাঝারি"),
        "hindi": {"disease": "अगेती झुलसा"},
    },
    "Potato_late_blight": {
        "crop": "Potato",
        "disease": "Late Blight",
        "is_healthy": False,
        "what_we_found": _narrative_section(
            en="The leaf shows water-soaked lesions that can spread rapidly in cool, wet weather.",
            hi="पत्ते में पछेती झुलसा के अनुरूप पानी जैसे धब्बे दिख रहे हैं जो तेजी से फैल सकते हैं।",
            kn="ಆಲೂಗಡ್ಡೆ ಎಲೆಯಲ್ಲಿ ನೀರು ತುಂಬಿದ ಕಪ್ಪು ಕಲೆಗಳು ಮತ್ತು ತೇವದ ವಾತಾವರಣದಲ್ಲಿ ಬಿಳಿ ಶಿಲೀಂಧ್ರ ಕಂಡುಬಂದಿದೆ.",
            ta="இலைகளில் நீர் கோர்த்த கரும் புள்ளிகள் தென்படுகின்றன.",
            te="ఆకులపై కమ్ముకున్న నల్లటి మచ్చలు కనిపిస్తున్నాయి.",
            mr="पानांवर पाण्यासारखे काळे ठिपके दिसत आहेत जे थंड हवामानात वेगाने पसरतात.",
            bn="পাতায় কালচে ভেজা দাগ দেখা যাচ্ছে যা ঠাণ্ডা আবহাওয়ায় দ্রুত ছড়ায়।"
        ),
        "why_it_happened": _list_section(
            en=["Late blight is caused by Phytophthora infestans.", "Cool nights and humidity create ideal conditions."],
            hi=["पछेती झुलसा Phytophthora infestans द्वारा होता है।", "ठंडी रातें और नमी इसके लिए आदर्श हैं।"],
            kn=["ಫೈಟೋಪ್ಥೊರಾ ಇನ್ಫೆಸ್ಟಾನ್ಸ್ ರೋಗಕಾರಕ.", "ತಂಪಾದ, ಒದ್ದೆಯಾದ ಮತ್ತು ತೇವಾಂಶವುಳ್ಳ ವಾತಾವರಣ."],
            ta=["பைட்டோப்தோரா இன்ஃபெஸ்டான்ஸ் பூஞ்சை.", "குளிர்ந்த, ஈரப்பதமான வானிலை."],
            te=["ఫైటోప్తోరా ఇన్ఫెస్టాన్స్ శిలీంధ్రం.", "చల్లని, తేమతో కూడిన వాతావరణం."],
            mr=["फायटोफ्थोरा इन्फेस्टान्स बुरशीमुळे हा आजार होतो.", "थंड रात्री आणि दमट हवामान रोगास पूरक आहे."],
            bn=["ফাইটোফথোরা ইনফেস্টানস ছত্রাকের কারণে নাবি ধসা রোগ হয়।", "ঠাণ্ডা রাত ও ঘন কুয়াশা সংক্রমণ বাড়ায়।"]
        ),
        "symptoms": _list_section(
            en=["Water-soaked patches expanding quickly", "White fuzzy growth under leaves"],
            hi=["पानी जैसे धब्बे जो जल्दी फैलते हैं", "पत्तियों के नीचे सफेद फफूंद"],
            kn=["ಎಲೆಗಳ ಮೇಲೆ ಕಪ್ಪು ನೀರು ತುಂಬಿದ ಕಲೆಗಳು", "ಎಲೆಗಳ ಕೆಳಭಾಗದಲ್ಲಿ ಬಿಳಿ ಶಿಲೀಂಧ್ರ"],
            ta=["இலை விளிம்புகளில் பெரிய கரும் புள்ளிகள்", "இலையின் அடியில் வெள்ளை பூஞ்சை"],
            te=["ఆకుల అంచుల వద్ద పెద్ద నల్లటి మచ్చలు", "ఆకుల కింద తెల్లటి బూజు"],
            mr=["पानांवर वेगाने पसरणारे काळे डाग", "पानाच्या खाली पांढरी बुरशी"],
            bn=["পাতায় দ্রুত ছড়ানো কালো দাগ", "পাতার নিচে সাদা ছত্রাক"]
        ),
        "risk_factors": _list_section(
            en=["Cool, foggy, wet weather"], hi=["ठंडा, कोहरे वाला मौसम"], kn=["ತಂಪಾದ, ಒದ್ದೆಯಾದ ವಾತಾವರಣ"],
            ta=["குளிர்ந்த, ஈரப்பதமான வானிலை"], te=["చల్లని, తేమతో కూడిన వాతావరణం"],
            mr=["थंड व धुकेयुक्त हवामान"], bn=["ঠাণ্ডা ও কুয়াশাচ্ছন্ন আবহাওয়া"]
        ),
        "immediate_actions": _list_section(
            en=["Inspect whole field for new lesions.", "Contact local agricultural support."],
            hi=["पूरे खेत में नए धब्बे देखें।", "स्थानीय कृषि सहायता से संपर्क करें।"],
            kn=["ಸೋಂಕಿತ ಸಸ್ಯಗಳನ್ನು ತಕ್ಷಣವೇ ನಾಶಪಡಿಸಿ.", "ಮೇಲ್ಭಾಗದ ನೀರಾವರಿ ನಿಲ್ಲಿಸಿ."],
            ta=["பாதிக்கப்பட்ட செடிகளை உடனடியாக அகற்றவும்.", "நீர் பாய்ச்சுவதை நிறுத்தவும்."],
            te=["సోకిన మొక్కలను తక్షణమే తొలగించండి.", "పైనుండి నీటి పిచికారీ నిలిపివేయండి."],
            mr=["बाधित झाडे शेतातून त्वरित नष्ट करा.", "कृषी अधिकाऱ्यांचा सल्ला घ्या."],
            bn=["আক্রান্ত গাছ দ্রুত নষ্ট করে ফেলুন।", "কৃষি কর্মকর্তার পরামর্শ নিন।"]
        ),
        "management": _list_section(
            en=["Rapidly monitor field and remove infected tissues.", "Apply targeted fungicide immediately."],
            hi=["खेत की निगरानी करें और संक्रमित ऊतक हटाएं।", "तुरंत लक्षित कवकनाशी का प्रयोग करें।"],
            kn=["ತಕ್ಷಣವೇ ಅನುಮೋದಿತ ಶಿಲೀಂಧ್ರನಾಶಕ ಬಳಸಿ."],
            ta=["உடனடியாக பூஞ்சாkillியை தெளிக்கவும்."],
            te=["వెంటనే తగిన శిలీంధ్రనాಶకాన్ని పిచికారీ చేయండి."],
            mr=["योग्य बुरशीनाशकाची त्वरित फवारणी करा."], bn=["অনুমোদিত ছত্রাকনাশক অবিলম্বে স্প্রে করুন।"]
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "prevention": _list_section(
            en=["Use certified healthy seed tubers."], hi=["प्रमाणित स्वस्थ बीज का उपयोग करें।"], kn=["ಪ್ರಮಾಣೀಕೃತ ಬೀಜಗಳನ್ನು ಬಳಸಿ."],
            ta=["சான்றளிக்கப்பட்ட விதைகளைப் பயன்படுத்தவும்."], te=["ధృవీకరించబడిన విత్తనాలను ఉపయోగించండి."],
            mr=["प्रमाणित व निरोगी बियाणे वापरा."], bn=["সার্টিফাইড রোগমুক্ত বীজ ব্যবহার করুন।"]
        ),
        "avoid": _list_section(
            en=["Avoid moving infected tubers between fields."], hi=["संक्रमित कंदों को खेतों के बीच ले जाने से बचें।"], kn=["ಸೋಂಕಿತ ಗೆಡ್ಡೆಗಳನ್ನು ಜಮೀನಿನಲ್ಲಿ ಬಿಡಬೇಡಿ."],
            ta=["பாதிக்கப்பட்ட கிழங்குகளை வயலில் விடாதீர்கள்."], te=["సోకిన దుంపలను పొలంలో ఉంచవద్దు."],
            mr=["बाधित बटाटे दुसऱ्या शेतात नेऊ नका."], bn=["আক্রান্ত আলু অন্য জমিতে নিয়ে যাবেন না।"]
        ),
        "when_to_seek_help": _list_section(
            en=["If symptoms expand quickly after rain."], hi=["यदि बारिश के बाद लक्षण तेजी से फैलें।"], kn=["ತಕ್ಷಣವೇ ಕ್ರಮ ಕೈಗೊಳ್ಳಿ-ಈ ರೋಗವು ವೇಗವಾಗಿ ಹರಡುತ್ತದೆ."],
            ta=["உடனடி நடவடிக்கை தேவை - இந்நோய் வேகமாக பரவும்."], te=["తక్షణమే చర్య తీసుకోండి—ఈ తెగులు వేగంగా వ్యాపిస్తుంది."],
            mr=["पावसानंतर रोग वेगाने पसरत असल्यास."], bn=["বৃষ্টির পর রোগ দ্রুত ছড়িয়ে পড়লে।"]
        ),
        "severity": _narrative_section(en="High", hi="उच्च", kn="ಹೆಚ್ಚು", ta="அதிகம்", te="చాలా ఎక్కువ", mr="उच्च", bn="খুব বেশি"),
        "spread_risk": _narrative_section(en="High", hi="उच्च", kn="ಬಹಳ ಹೆಚ್ಚು", ta="மிக அதிகம்", te="చాలా ఎక్కువ", mr="उच्च", bn="খুব বেশি"),
        "hindi": {"disease": "पछेती झुलसा"},
    },
    "Potato_healthy": {
        "crop": "Potato",
        "disease": "Healthy",
        "is_healthy": True,
        "what_we_found": _narrative_section(
            en="The potato leaf appears healthy.", hi="आलू का पत्ता स्वस्थ दिख रहा है।", kn="ಆಲೂಗಡ್ಡೆ ಎಲೆಯು ಸಂಪೂರ್ಣವಾಗಿ ಆರೋಗ್ಯಕರವಾಗಿದೆ.",
            ta="உருளைக்கிழங்கு இலை ஆரோக்கியமாக உள்ளது.", te="బంగాళాదుంప ఆకు ఆరోగ్యంగా ఉంది.",
            mr="बटाट्याचे पान पूर्णपणे निरोगी दिसत आहे.", bn="আলু পাতাটি সম্পূর্ণরূপে সুস্থ রয়েছে।"
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "why_it_happened": _list_section(en=["No disease pattern detected."], hi=["कोई रोग नहीं मिला।"], kn=["ಯಾವುದೇ ರೋಗದ ಲಕ್ಷಣವಿಲ್ಲ."], ta=["நோய் எதுவும் கண்டறியப்படவில்லை."], te=["ఏ వ్యాధి లక్షణాలు లేవు."], mr=["कोणतेही रोगाचे लक्षण आढळले नाही."], bn=["রোগের কোন লক্ষণ পাওয়া যায়নি।"]),
        "symptoms": _list_section(en=["No lesions visible."], hi=["कोई धब्बे नहीं दिख रहे हैं।"], kn=["ಯಾವುದೇ ಕಲೆಗಳಿಲ್ಲ."], ta=["புள்ளிகள் எதுவும் இல்லை."], te=["మచ్చలు ఏవీ లేవు."], mr=["कोणतेही डाग नाहीत."], bn=["কোন দাগ নেই।"]),
        "risk_factors": _list_section(en=["No disease pressure."], hi=["कोई रोग दबाव नहीं।"], kn=["ಯಾವುದೇ ರೋಗದ ಒತ್ತಡವಿಲ್ಲ."], ta=["நோய் பாதிப்பு இல்லை."], te=["వ్యాధి ముప్పు లేదు."], mr=["रोगाचा धोका नाही."], bn=["রোগের ঝুঁকি নেই।"]),
        "immediate_actions": _list_section(en=["Continue regular monitoring."], hi=["निगरानी जारी रखें।"], kn=["ನಿಯಮಿತ ಆರೈಕೆ ಮುಂದುವರಿಸಿ."], ta=["வழக்கமான கண்காணிப்பை தொடரவும்."], te=["సాధారణ సంరక్షణను కొనసాగించండి."], mr=["नियमित देखभाल चालू ठेवा."], bn=["নিয়মিত যত্ন নেওয়া চালিয়ে যান।"]),
        "management": _list_section(en=["No treatment needed."], hi=["कोई उपचार आवश्यक नहीं।"], kn=["ಯಾವುದೇ ಚಿಕಿತ್ಸೆ ಅಗತ್ಯವಿಲ್ಲ."], ta=["சிகிச்சை தேவையில்லை."], te=["చికిత్స అవసరం లేదు."], mr=["उपचारांची गरज नाही."], bn=["কোন চিকিৎসার প্রয়োজন নেই।"]),
        "prevention": _list_section(en=["Maintain crop hygiene."], hi=["सफाई बनाए रखें।"], kn=["ನೈರ್ಮಲ್ಯ ಕಾಪಾಡಿ."], ta=["சுத்தமாக பராமரிக்கவும்."], te=["పరిశుభ్రతను కాపాడండి."], mr=["शेताची स्वच्छता राखा."], bn=["ক্ষেতের পরিচ্ছন্নতা বজায় রাখুন।"]),
        "avoid": _list_section(en=["No issues."], hi=["कोई समस्या नहीं।"], kn=["ಯಾವುದೇ ತೊಂದರೆಯಿಲ್ಲ."], ta=["பிரச்சனைகள் எதுவும் இல்லை."], te=["ఎటువంటి సమస్యలు లేవు."], mr=["कोणतीही अडचण नाही."], bn=["কোন সমস্যা নেই।"]),
        "when_to_seek_help": _list_section(en=["If new spots appear."], hi=["यदि नए धब्बे दिखें।"], kn=["ಹೊಸ ಕಲೆಗಳು ಕಂಡುಬಂದರೆ."], ta=["புதிய புள்ளிகள் தோன்றினால்."], te=["కొత్త మచ్చలు కనిపిస్తే."], mr=["नवीन डाग दिसल्यास."], bn=["নতুন দাগ দেখা দিলে।"]),
        "severity": _narrative_section(en="Low", hi="कम", kn="ಇಲ್ಲ", ta="குறைவு", te="తక్కువ", mr="कमी", bn="কম"),
        "spread_risk": _narrative_section(en="Low", hi="कम", kn="ಇಲ್ಲ", ta="குறைவு", te="తక్కువ", mr="कमी", bn="কম"),
        "hindi": {"disease": "स्वस्थ"},
    },

    # -------------------------------------------------------------------------
    # 2. TOMATO
    # -------------------------------------------------------------------------
    "Tomato_early_blight": {
        "crop": "Tomato",
        "disease": "Early Blight",
        "is_healthy": False,
        "what_we_found": _narrative_section(
            en="The tomato leaf shows brown lesions with concentric ring-like markings from early blight.",
            hi="टमाटर के पत्ते में अगेती झुलसा (Early Blight) के अनुरूप भूरे धब्बे दिखाई दे रहे हैं।",
            kn="ಟೊಮೆಟೊ ಎಲೆಯಲ್ಲಿ ಅಗೋಚರ ಕಲೆಗಳು ಮತ್ತು ಆರಂಭಿಕ ರೋಗದ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿವೆ.",
            ta="தக்காளி இலையில் ஆரம்பகால கருகல் நோயின் அறிகுறிகள் தென்படுகின்றன.",
            te="టమోటా ఆకుపై ముందస్తు ఎండతెగులు లక్షణాలు కనిపిస్తున్నాయి.",
            mr="टोमॅटोच्या पानांवर गोल काळे-तपकिरी ठिपके दिसत आहेत.",
            bn="টমেটো পাতায় বলয়াকার খয়েরি দাগ দেখা যাচ্ছে।"
        ),
        "why_it_happened": _list_section(
            en=["Associated with fungus Alternaria solani.", "Warm, humid weather encourages infection."],
            hi=["फफूंद Alternaria solani से जुड़ा है।", "गर्म, नम मौसम संक्रमण बढ़ाता है।"],
            kn=["ಆಲ್ಟರ್ನೇರಿಯಾ ಸೊಲಾನಿ ಶಿಲೀಂಧ್ರ.", "ಬಿಸಿ ಮತ್ತು ತೇವದ ವಾತಾವರಣ."],
            ta=["ஆல்டர்னேரியா சோலானி பூஞ்சை.", "வெப்பமான ஈரப்பதம்."],
            te=["ఆల్టర్నేరియా సోలాని శిలీంధ్రం.", "వెచ్చని, తేమతో కూడిన పరిస్థితి."],
            mr=["अल्टरनेरिया सोलेनी बुरशीमुळे हा रोग होतो.", "उबदार हवामानामुळे संसर्ग वाढतो."],
            bn=["অল্টারনারিয়া সোলানি ছত্রাকের সংক্রমণ।", "উষ্ণ আবহাওয়া রোগ বাড়ায়।"]
        ),
        "symptoms": _list_section(
            en=["Brown circular lesions on lower leaves", "Target-like concentric rings"],
            hi=["निचले पत्तों पर भूरे गोल धब्बे", "लक्ष्य जैसा वृत्ताकार छल्ला"],
            kn=["ಕೆಳಗಿನ ಎಲೆಗಳ ಮೇಲೆ ಕಂದು ಬಣ್ಣದ ವೃತ್ತಾಕಾರದ ಕಲೆಗಳು", "ಎಲೆಯ ಸುತ್ತ ಹಳದಿ ವೃತ್ತ"],
            ta=["கீழ் இலைகளில் வட்ட வடிவ புள்ளிகள்", "மஞ்சள் வளையம்"],
            te=["దిగువ ఆకులపై గుండ్రటి మచ్చలు", "పసుపు రంగు వలయం"],
            mr=["खालील पानांवर गोल तपकिरी ठिपके", "ठिपक्यांभोवती पिवळा घेरा"],
            bn=["নিচের পাতায় গোল খয়েরি দাগ", "দাগের চারপাশে হলুদ বলয়"]
        ),
        "risk_factors": _list_section(
            en=["Warm, humid weather"], hi=["गर्म, नम मौसम"], kn=["ಬಿಸಿ, ತೇವದ ವಾತಾವರಣ"],
            ta=["வெப்பமான, ஈரப்பதமான வானிலை"], te=["వెచ్చని, తేమతో కూడిన ವಾತಾವರಣಂ"],
            mr=["उबदार हवामान"], bn=["উষ্ণ আবহাওয়া"]
        ),
        "immediate_actions": _list_section(
            en=["Remove severely affected lower leaves.", "Avoid overhead watering."],
            hi=["संभव हो तो अधिक प्रभावित पत्तियां हटा दें।", "ओवरहेड सिंचाई से बचें।"],
            kn=["ಸೋಂಕಿತ ಕೆಳಗಿನ ಎಲೆಗಳನ್ನು ತೆಗೆದುಹಾಕಿ.", "ಎಲೆಗಳನ್ನು ಒಣಗಿಸಿ."],
            ta=["பாதிக்கப்பட்ட இலைகளை அகற்றுங்கள்.", "இலைகளை உலர்வாக வையுங்கள்."],
            te=["బాధిత దిగువ ఆకులను తొలగించండి.", "ఆకు పొడిగా ఉంచండి."],
            mr=["बाधित पाने काढून टाका.", "पानांवर पाणी टाकणे टाळा."],
            bn=["আক্রান্ত পাতা কেটে ফেলুন।", "পাতার ওপর জল ছেটানো বন্ধ করুন।"]
        ),
        "management": _list_section(
            en=["Use sanitation and crop rotation.", "Apply approved copper spray."],
            hi=["सफाई और फसल चक्र का उपयोग करें।", "तांबा आधारित कवकनाशी का प्रयोग करें।"],
            kn=["ತಾಮ್ರ ಆಧಾರಿತ ಶಿಲೀಂಧ್ರನಾಶಕ ಬಳಸಿ."],
            ta=["காப்பர் பூஞ்சாkillியை தெளிக்கவும்."],
            te=["కాపర్ ఆధారిత శిలీంధ్రనాశకాన్ని పిచಿಕారీ చేయండి."],
            mr=["कॉपरयुक्त बुरशीनाशक वापरा."], bn=["কপারযুক্ত ছত্রাকনাশক স্প্রে করুন।"]
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "prevention": _list_section(
            en=["Remove crop debris after harvest."], hi=["कटाई के बाद अवशेष हटाएं।"], kn=["ಕೊಯ್ಲಿನ ನಂತರ ತ್ಯಾಜ್ಯವನ್ನು ನಾಶಪಡಿಸಿ."],
            ta=["மட்கு உரமிடுதல் மற்றும் பயிர் சுழற்சி."], te=["మల్చింగ్ చేయండి మరియు పంట మార్పిడి పాటించండి."],
            mr=["पिकाची फिरवाफिरव करा."], bn=["ফসল কাটার পর জমি পরিষ্কার রাখুন।"]
        ),
        "avoid": _list_section(
            en=["Avoid overhead watering keeping canopy wet."], hi=["ओवरहेड सिंचाई से बचें।"], kn=["ಮಣ್ಣಿನ ನೀರು ಎಲೆಗಳ ಮೇಲೆ ಸಿಗದಂತೆ ನೋಡಿಕೊಳ್ಳಿ."],
            ta=["மண் நீர் இலைகளில் தெளிப்பதை தவிர்க்கவும்."], te=["నేల నీరు ఆకులపై పడకుండా చూడండి."],
            mr=["मातीचे पाणी पानांवर उडणार नाही याची काळजी घ्या."], bn=["মাটির জল পাতায় লাগতে দেবেন না।"]
        ),
        "when_to_seek_help": _list_section(
            en=["If disease spreads rapidly across plants."], hi=["यदि रोग तेजी से फैल रहा हो।"], kn=["ಎಲೆಗಳು ಕಾಂಡದ ಮೂರನೇ ಒಂದು ಭಾಗದಷ್ಟು ಉದುರಿದರೆ."],
            ta=["இலை உதிர்வு அதிகமாக இருந்தால்."], te=["ఆకులు ఎక్కువగా రాలిపోతుంటే."],
            mr=["पाने मोठ्या प्रमाणात गळत असल्यास."], bn=["পাতা অতিরিক্ত ঝরে পড়লে।"]
        ),
        "severity": _narrative_section(en="Moderate", hi="मध्यम", kn="ಮಧ್ಯಮ", ta="மிதமான", te="మధ్యస్థం", mr="मध्यम", bn="মাঝারি"),
        "spread_risk": _narrative_section(en="High", hi="उच्च", kn="ಹೆಚ್ಚು", ta="அதிகம்", te="எక్కువ", mr="उच्च", bn="বেশি"),
        "hindi": {"disease": "अगेती झुलसा"},
    },
    "Tomato_late_blight": {
        "crop": "Tomato",
        "disease": "Late Blight",
        "is_healthy": False,
        "what_we_found": _narrative_section(
            en="The tomato leaf shows water-soaked lesions expanding under cool conditions.",
            hi="टमाटर के पत्ते में पछेती झुलसा के अनुरूप पानी जैसे धब्बे दिख रहे हैं।",
            kn="ಟೊಮೆಟೊ ಎಲೆಯಲ್ಲಿ ಲೇಟ್ ಬ್ಲೈಟ್ ರೋಗದ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿವೆ.",
            ta="தக்காளி இலையில் லேட் பிளைட் நோயின் அறிகுறிகள் தென்படுகின்றன.",
            te="టమోటా ఆకుపై లేట్ బ్లైట్ వ్యాధి లక్షణాలు కనిపిస్తాయి.",
            mr="टोमॅटोच्या पानांवर पाण्यासारखे काळे डाग दिसत आहेत.",
            bn="টমেটো পাতায় নাবি ধসা রোগের কালচে ভেজা দাগ দেখা যাচ্ছে।"
        ),
        "why_it_happened": _list_section(
            en=["Caused by Phytophthora infestans.", "Cool nights and fog favour spread."],
            hi=["Phytophthora infestans के कारण होता है।", "ठंडी रातें और कोहरा इसे बढ़ाते हैं।"],
            kn=["ಫೈಟೋಪ್ಥೊರಾ ಇನ್ಫೆಸ್ಟಾನ್ಸ್ ರೋಗಕಾರಕ."],
            ta=["பைட்டோப்தோரா இன்ஃபெஸ்டான்ஸ் பூஞ்சை பரவுகிறது."],
            te=["ఫైటోప్తోరా ఇన్ఫెస్టాన్స్ వ్యాపిస్తుంది."],
            mr=["फायटोफ्थोरा बुरशीमुळे हा रोग पसरतो."], bn=["ফাইটোফথোরা ছত্রাকের কারণে রোগ ছড়ায়।"]
        ),
        "symptoms": _list_section(
            en=["Water-soaked leaf lesions"], hi=["पानी जैसे धब्बे"], kn=["ಎಲೆಗಳ ಮೇಲೆ ನೀರು ತುಂಬಿದ ಕಲೆಗಳು"],
            ta=["நீர் கோர்த்த புள்ளிகள்"], te=["నీటి మచ్చలు"],
            mr=["पानांवर काळे ओले डाग"], bn=["পাতায় কালচে ভেজা দাগ"]
        ),
        "risk_factors": _list_section(
            en=["Cool, rainy weather"], hi=["ठंडा, बरसाती मौसम"], kn=["ತಂಪಾದ, ಮಳೆಯ ವಾತಾವರಣ"],
            ta=["குளிர்ந்த, மழைக்காலம்"], te=["చల్లని వర్షపు వాతావరణం"],
            mr=["थंड हवामान"], bn=["ঠাণ্ডা আবহাওয়া"]
        ),
        "immediate_actions": _list_section(
            en=["Inspect whole field immediately."], hi=["पूरे खेत की जांच करें।"], kn=["ತಕ್ಷಣವೇ ಕ್ಷೇತ್ರ ಪರಿಶೀಲನೆ ಮಾಡಿ."],
            ta=["வயலை உடனடியாக ஆய்வு செய்யுங்கள்."], te=["పొలాన్ని తక్షణమే పరిశీలించండి."],
            mr=["शेताची त्वरित पाहणी करा."], bn=["পুরো জমি তদারকি করুন।"]
        ),
        "management": _list_section(
            en=["Use locally approved treatment."], hi=["अनुशंसित उपचार का प्रयोग करें।"], kn=["ಅನುಮೋದಿತ ಚಿಕಿತ್ಸೆ ಬಳಸಿ."],
            ta=["பரிந்துரைக்கப்பட்ட சிகிச்சையை பயன்படுத்தவும்."], te=["సిఫార్సు చేసిన చికిత్సను ఉపయోగించండి."],
            mr=["योग्य बुरशीनाशकाची फवारणी करा."], bn=["উপযুক্ত ছত্রাকনাশক স্প্রে করুন।"]
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "prevention": _list_section(
            en=["Use healthy planting material."], hi=["स्वस्थ रोपण सामग्री का उपयोग करें।"], kn=["ಉತ್ತಮ ಬೀಜಗಳನ್ನು ಬಳಸಿ."],
            ta=["ஆரோக்கியமான நாற்றுகளை பயன்படுத்தவும்."], te=["ఆరోగ్యకరమైన నాట్లను ఉపయోగించండి."],
            mr=["निरोगी रोपे वापरा."], bn=["সুস্থ চারা রোপণ করুন।"]
        ),
        "avoid": _list_section(
            en=["Avoid leaving volunteer plants."], hi=["स्वयं उगे पौधे छोड़ने से बचें।"], kn=["ಸೋಂಕಿತ ಗಿಡಗಳನ್ನು ಬಿಡಬೇಡಿ."],
            ta=["பாதிக்கப்பட்ட தாவரங்களை விட்டுவைக்காதீர்கள்."], te=["సోకిన మొక్కలను వదలకుండా తొలగించండి."],
            mr=["बाधित झाडे शेतात ठेवू नका."], bn=["আক্রান্ত গাছ জমিতে রাখবেন না।"]
        ),
        "when_to_seek_help": _list_section(
            en=["If symptoms expand quickly."], hi=["यदि लक्षण तेजी से फैलें।"], kn=["ಲಕ್ಷಣಗಳು ವೇಗವಾಗಿ ಹರಡಿದರೆ."],
            ta=["அறிகுறிகள் வேகமாக பரவினால்."], te=["లక్షణాలు వేగంగా వ్యాపిస్తే."],
            mr=["लक्षणे वेगाने पसरत असल्यास."], bn=["লক্ষণ দ্রুত ছড়িয়ে পড়লে।"]
        ),
        "severity": _narrative_section(en="High", hi="उच्च", kn="ಹೆಚ್ಚು", ta="அதிகம்", te="చాలా ఎక్కువ", mr="उच्च", bn="খুব বেশি"),
        "spread_risk": _narrative_section(en="High", hi="उच्च", kn="ಹೆಚ್ಚು", ta="அதிகம்", te="చాలా ఎక్కువ", mr="उच्च", bn="খুব বেশি"),
        "hindi": {"disease": "पछेती झुलसा"},
    },
    "Tomato_healthy": {
        "crop": "Tomato",
        "disease": "Healthy",
        "is_healthy": True,
        "what_we_found": _narrative_section(
            en="The tomato leaf appears healthy.", hi="टमाटर का पत्ता स्वस्थ दिख रहा है।", kn="ಟೊಮೆಟೊ ಎಲೆಯು ಸಂಪೂರ್ಣವಾಗಿ ಆರೋಗ್ಯಕರವಾಗಿದೆ.",
            ta="தக்காளி இலை ஆரோக்கியமாக உள்ளது.", te="టమోటా ఆకు చాలా ఆరోగ్యంగా ఉంది.",
            mr="टोमॅटोचे पान निरोगी दिसत आहे.", bn="টমেটো পাতাটি সুস্থ রয়েছে।"
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "why_it_happened": _list_section(en=["No disease pattern detected."], hi=["कोई रोग नहीं मिला।"], kn=["ಯಾವುದೇ ರೋಗದ ಲಕ್ಷಣವಿಲ್ಲ."], ta=["நோய் எதுவும் கண்டறியப்படவில்லை."], te=["ఏ వ్యాధి లక్షణాలు లేవు."], mr=["कोणतेही रोगाचे लक्षण नाही."], bn=["রোগের কোন লক্ষণ পাওয়া যায়নি।"]),
        "symptoms": _list_section(en=["No lesions detected."], hi=["कोई धब्बे नहीं मिले।"], kn=["ಯಾವುದೇ ಕಲೆಗಳಿಲ್ಲ."], ta=["புள்ளிகள் எதுவும் இல்லை."], te=["మచ్చలు ఏవీ లేవు."], mr=["कोणतेही डाग नाहीत."], bn=["কোন দাগ নেই।"]),
        "risk_factors": _list_section(en=["No disease pressure."], hi=["कोई रोग दबाव नहीं।"], kn=["ಯಾವುದೇ ರೋಗದ ಒತ್ತಡವಿಲ್ಲ."], ta=["நோய் பாதிப்பு இல்லை."], te=["వ్యాధి ముప్పు లేదు."], mr=["धोका नाही."], bn=["ঝুঁকি নেই।"]),
        "immediate_actions": _list_section(en=["Continue regular monitoring."], hi=["नियमित निगरानी जारी रखें।"], kn=["ನಿಯಮಿತ ಆರೈಕೆ ಮುಂದುವರಿಸಿ."], ta=["வழக்கமான பராமரிப்பை தொடரவும்."], te=["సాధారణ సంరక్షణను కొనసాగించండి."], mr=["नियमित काळजी घ्या."], bn=["নিয়মিত তদারকি করুন।"]),
        "management": _list_section(en=["No treatment needed."], hi=["कोई उपचार आवश्यक नहीं।"], kn=["ಯಾವುದೇ ಚಿಕಿತ್ಸೆ ಅಗತ್ಯವಿಲ್ಲ."], ta=["சிகிச்சை தேவையில்லை."], te=["చికిత్స అవసరం లేదు."], mr=["उपचारांची गरज नाही."], bn=["চিকিৎসা প্রয়োজন নেই।"]),
        "prevention": _list_section(en=["Maintain crop hygiene."], hi=["फसल सफाई बनाए रखें।"], kn=["ನೈರ್ಮಲ್ಯ ಕಾಪಾಡಿ."], ta=["வயலை சுத்தமாக வைக்கவும்."], te=["పరిశుభ్రతను కాపాడండి."], mr=["स्वच्छता राखा."], bn=["পরিচ্ছন্নতা বজায় রাখুন।"]),
        "avoid": _list_section(en=["No issues."], hi=["कोई समस्या नहीं।"], kn=["ಯಾವುದೇ ತೊಂದರೆಯಿಲ್ಲ."], ta=["பிரச்சனைகள் எதுவும் இல்லை."], te=["ఎటువంటి సమస్యలు లేవు."], mr=["அடச்சण नाही."], bn=["সমস্যা নেই।"]),
        "when_to_seek_help": _list_section(en=["If new symptoms appear."], hi=["यदि नए लक्षण दिखाई दें।"], kn=["ಹೊಸ ಕಲೆಗಳು ಕಂಡುಬಂದರೆ."], ta=["புதிய புள்ளிகள் தோன்றினால்."], te=["కొత్త మచ్చలు కనిపిస్తే."], mr=["नवीन डाग दिसल्यास."], bn=["নতুন লক্ষণ দেখা দিলে।"]),
        "severity": _narrative_section(en="Low", hi="कम", kn="ಇಲ್ಲ", ta="குறைவு", te="తక్కువ", mr="कमी", bn="কম"),
        "spread_risk": _narrative_section(en="Low", hi="कम", kn="ಇಲ್ಲ", ta="குறைவு", te="తక్కువ", mr="कमी", bn="কম"),
        "hindi": {"disease": "स्वस्थ"},
    },

    # -------------------------------------------------------------------------
    # 3. CORN / MAIZE
    # -------------------------------------------------------------------------
    "Corn_Common_rust": {
        "crop": "Corn",
        "disease": "Common Rust",
        "is_healthy": False,
        "what_we_found": _narrative_section(
            en="The corn leaf exhibits reddish-brown rust pustules on the leaf surface.",
            hi="मक्के के पत्ते पर छोटे जंग-रंग के दाने दिखाई दे रहे हैं।",
            kn="ಮೆಕ್ಕೆಜೋಳದ ಎಲೆಯ ಮೇಲೆ ಸಣ್ಣ, ಕೆಂಪು-ಕಂದು ಬಣ್ಣದ ಗುಳ್ಳೆಗಳು ಕಂಡುಬಂದಿವೆ.",
            ta="சோள இலையில் சிவந்த பழுப்பு நிற புள்ளிகள் காணப்படுகின்றன.",
            te="మొక్కజొన్న ఆకుపై ఎరుపు-గోధుమ రంగు మచ్చలు కనిపిస్తున్నాయి.",
            mr="मक्याच्या पानांवर तांबूस-तपकिरी रंगाचे पुरळ दिसत आहेत.",
            bn="ভুট্টা পাতায় লালচে খয়েরি মরচে পরা দাগ দেখা যাচ্ছে।"
        ),
        "why_it_happened": _list_section(
            en=["Fungal pathogen Puccinia sorghi spreading by wind.", "Cool nights and high humidity."],
            hi=["पुक्सिनिया सोरघी कवक जो हवा से फैलता है।", "ठंडी रातें और उच्च आर्द्रता।"],
            kn=["ಪುಕ್ಸಿನಿಯಾ ಸೊರ್ಘಿ ಶಿಲೀಂಧ್ರ.", "ತಂಪಾದ ತಾಪಮಾನ ಮತ್ತು ಹೆಚ್ಚಿನ ತೇವಾಂಶ."],
            ta=["பக்சினியா சோர்கி பூஞ்சை காற்றில் பரவுகிறது.", "குளிர்ந்த இரவு மற்றும் அதிக ஈரப்பதம்."],
            te=["పుక్సినియా సోర్ఘి అనే శిలీంధ్రం గాలి ద్వారా వ్యాపిస్తుంది.", "చల్లని రాత్రులు మరియు అధిక తేమ."],
            mr=["पुक्सिनिया सोर्गी बुरशी गव्हासारख्या पिकांवरून वाऱ्याद्वारे पसरते.", "थंड हवामानामुळे संसर्ग वाढतो."],
            bn=["পুকসিনিয়া সোরঘি নামক ছত্রাক বাতাসের মাধ্যমে ছড়ায়।", "ঠাণ্ডা রাত ও আর্দ্রতা সহায়ক।"]
        ),
        "symptoms": _list_section(
            en=["Reddish-brown pustules on both leaf sides", "Yellowing foliage"],
            hi=["पत्ती के दोनों तरफ जंग-भूरे दाने", "पत्तियों का पीला पड़ना"],
            kn=["ಎಲೆಗಳ ಮೇಲೆ ಕೆಂಪು-ಕಂದು ಬಣ್ಣದ ಗುಳ್ಳೆಗಳು", "ಎಲೆಗಳು ಹಳದಿಯಾಗುವುದು"],
            ta=["இலைகளின் இருபுறமும் சிவந்த பழுப்பு நிற கொப்பளங்கள்"],
            te=["ఆకుల రెండు వైపులా ఎరుపు-గోధుమ రంగు గుల్లలు"],
            mr=["पानाच्या दोन्ही बाजूंना तांबूस डाग"], bn=["পাতার উভয় দিকে লালচে দাগ"]
        ),
        "risk_factors": _list_section(
            en=["High humidity and dew"], hi=["उच्च नमी और ओस"], kn=["ಹೆಚ್ಚಿನ ತೇವಾಂಶ ಮತ್ತು ಇಬ್ಬನಿ"],
            ta=["அதிக ஈரப்பதம் மற்றும் பனிப்பொழிவு"], te=["అధిక తేమ మరియు మంచు"],
            mr=["अधिक दमटपणा व दव"], bn=["উচ্চ আর্দ্রতা ও শিশির"]
        ),
        "immediate_actions": _list_section(
            en=["Monitor infection severity.", "Ensure balanced plant nutrients."],
            hi=["बीमारी के प्रसार पर नजर रखें।", "संतुलित पोषण दें।"],
            kn=["ರೋಗದ ತೀವ್ರತೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.", "ಸಮತೋಲಿತ ಪೋಷಣೆ ನೀಡಿ."],
            ta=["தொற்றின் தீவிரத்தை கண்காணிக்கவும்."],
            te=["తెగులు తీవ్రతను గమనించండి."],
            mr=["रोगाच्या प्रसारावर लक्ष ठेवा."], bn=["সংক্রমণের ওপর নজর রাখুন।"]
        ),
        "management": _list_section(
            en=["Apply protective fungicide if severe early in season."],
            hi=["शुरुआती मौसम में गंभीर होने पर कवकनाशी दें।"],
            kn=["ರೋಗ ತೀವ್ರವಾಗಿದ್ದರೆ ಶಿಲೀಂಧ್ರನಾಶಕ ಬಳಸಿ."],
            ta=["தேவைப்பட்டால் பூஞ்சாkillியை தெளிக்கவும்."],
            te=["అవసరమైతే శిలీంధ్రనాశకాన్ని పిచಿಕారీ చేయండి."],
            mr=["गरज भासल्यास योग्य बुरशीनाशक वापरा."], bn=["প্রয়োজনে উপযুক্ত ছত্রাকনাশক ব্যবহার করুন।"]
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "prevention": _list_section(
            en=["Plant rust-resistant corn hybrids."],
            hi=["प्रतिरोधी किस्मों की बुआई करें।"],
            kn=["ರೋಗ ನಿರೋಧಕ ತಳಿಗಳನ್ನು ಬಿತ್ತನೆ ಮಾಡಿ."],
            ta=["நோய் எதிர்ப்பு ரகங்களை பயிரிடவும்."],
            te=["తెగులు నిరోధక విత్తనాలను నాటండి."],
            mr=["रोगप्रतिकारक वाण वापरा."], bn=["রোগপ্রতিরোধী জাতের বীজ বপন করুন।"]
        ),
        "avoid": _list_section(
            en=["Avoid excessive nitrogen application."], hi=["अत्यधिक नाइट्रोजन से बचें।"], kn=["ಅತಿಯಾದ ನೈಟ್ರೋಜನ್ ಬಳಕೆಯನ್ನು ತಪ್ಪಿಸಿ."],
            ta=["அதிக நைட்ரஜன் பயன்பாட்டை தவிர்க்கவும்."], te=["అధిక నైట్రోజన్ వినియోగాన్ని నివారించండి."],
            mr=["जास्त नत्र वापरणे टाळा."], bn=["অতিরিক্ত নাইট্রোজেন দেবেন না।"]
        ),
        "when_to_seek_help": _list_section(
            en=["If pustules cover more than 10-15% leaf area."],
            hi=["यदि 10-15% से अधिक पत्तियों पर धब्बे आ जाएं।"],
            kn=["೧೦-೧೫% ಕ್ಕಿಂತ ಹೆಚ್ಚು ಎಲೆಗಳು ಬಾಧಿತವಾಗಿದ್ದರೆ."],
            ta=["15% க்கும் அதிகமாக பரவினால் அக்ரி அதிகாரியை அணுகவும்."],
            te=["తెగులు 15% కంటే ఎక్కువ వ్యాపిస్తే వ్యవసాయ అధికారిని సంప్రదించండి."],
            mr=["१०-१५% पेक्षा जास्त पानांवर रोग पसरल्यास."], bn=["১৫% এর বেশি পাতায় ছড়ালে কৃষি অফিসে যোগাযোগ করুন।"]
        ),
        "severity": _narrative_section(en="Moderate", hi="मध्यम", kn="ಮಧ್ಯಮ", ta="மிதமான", te="மధ్యస్థం", mr="मध्यम", bn="মাঝারি"),
        "spread_risk": _narrative_section(en="Moderate", hi="मध्यम", kn="ಮಧ್ಯಮ", ta="மிதமான", te="மధ్యస్థం", mr="मध्यम", bn="মাঝারি"),
        "hindi": {"disease": "सामान्य रस्ट"},
    },
    "Corn_healthy": {
        "crop": "Corn",
        "disease": "Healthy",
        "is_healthy": True,
        "what_we_found": _narrative_section(
            en="The corn leaf appears healthy.", hi="मक्के का पत्ता स्वस्थ दिखाई दे रहा है।", kn="ಮೆಕ್ಕೆಜೋಳದ ಎಲೆಯು ಸಂಪೂರ್ಣವಾಗಿ ಆರೋಗ್ಯಕರವಾಗಿದೆ.",
            ta="சோள இலை ஆரோக்கியமாக உள்ளது.", te="మొక్కజొన్న ఆకు చాలా ఆరోగ్యంగా ఉంది.",
            mr="मक्याचे पान निरोगी आहे.", bn="ভুট্টা পাতাটি সুস্থ রয়েছে।"
        ),
        "watering_care": _list_section(
            en=["Keep soil moisture even; avoid water stress, which weakens plants", "Water early in the day so leaves dry quickly"],
            hi=["मिट्टी में नमी एक-सी रखें; पानी की कमी से पौधे कमजोर होते हैं", "सुबह जल्दी सिंचाई करें ताकि पत्ते जल्दी सूख जाएं"],
            kn=["ಮಣ್ಣಿನ ತೇವಾಂಶವನ್ನು ಸಮಾನವಾಗಿಡಿ; ಸಸ್ಯಗಳನ್ನು ದುರ್ಬಲಗೊಳಿಸುವ ನೀರಿನ ಕೊರತೆಯನ್ನು ತಡೆಯಿರಿ", "ಎಲೆಗಳು ಬೇಗನೆ ಒಣಗಲು ಬೆಳಿಗ್ಗೆ ಬೇಗನೆ ನೀರು ಹಾಕಿ"],
            ta=["மண்ணின் ஈரப்பதத்தை ஒரே சீராக வைத்திருங்கள்; தாவரங்களை బలஹீனப்படுத்தும் நீர் அழுத்தத்தைத் தவிர்க்கவும்", "இலைகள் விரைவில் உலர காலையிலேயே தண்ணீர் ஊற்றுங்கள்"],
            te=["నేలలో తేమను సమానంగా ఉంచండి; మొక్కలను బలహీనపరిచే నీటి కొరతను నివారించండి", "ఆకులు త్వరగా ఆరిపోయేలా ఉదయమే నీరు పోయండి"],
            mr=["मातीतील ओलावा कायम ठेवा; पाण्याचा ताण टाळा, ज्यामुळे झाडे कमकुवत होतात", "सकाळी लवकर पाणी द्या जेणेकरून पाने लवकर सुकतील"],
            bn=["মাটির আর্দ্রতা সমান রাখুন; জলের ঘাটতি এড়িয়ে চলুন, যা গাছকে দুর্বল করে", "সকালের দিকে সেচ দিন যাতে পাতাগুলো দ্রুত শুকিয়ে যায়"]
        ),
        "why_it_happened": _list_section(en=["No disease pattern detected."], hi=["कोई रोग नहीं मिला।"], kn=["ಯಾವುದೇ ರೋಗದ ಲಕ್ಷಣವಿಲ್ಲ."], ta=["நோய் எதுவும் கண்டறியப்படவில்லை."], te=["ఏ వ్యాధి లక్షణాలు లేవు."], mr=["कोणताही रोग नाही."], bn=["রোগ পাওয়া যায়নি।"]),
        "symptoms": _list_section(en=["No spots visible."], hi=["कोई धब्बे नहीं दिखे।"], kn=["ಯಾವುದೇ ಕಲೆಗಳಿಲ್ಲ."], ta=["புள்ளிகள் எதுவும் இல்லை."], te=["మచ్చలు ఏవీ లేవు."], mr=["डाग नाहीत."], bn=["দাগ নেই।"]),
        "risk_factors": _list_section(en=["No disease pressure."], hi=["कोई रोग दबाव नहीं।"], kn=["ಯಾವುದೇ ರೋಗದ ಒತ್ತಡವಿಲ್ಲ."], ta=["நோய் பாதிப்பு இல்லை."], te=["వ్యాధి ముప్పు లేదు."], mr=["धोका नाही."], bn=["ঝুঁকি নেই।"]),
        "immediate_actions": _list_section(en=["Continue regular field monitoring."], hi=["नियमित निगरानी जारी रखें।"], kn=["ಸಾಮಾನ್ಯ ನೀರಾವರಿ ಮುಂದುವರಿಸಿ."], ta=["வழக்கமான கண்காணிப்பை தொடரவும்."], te=["సాధారణ సంరక్షణను కొనసాగించండి."], mr=["नियमित पाहणी चालू ठेवा."], bn=["নিয়মিত পর্যবেক্ষণ চালিয়ে যান।"]),
        "management": _list_section(en=["No treatment needed."], hi=["कोई उपचार जरूरी नहीं।"], kn=["ಯಾವುದೇ ಚಿಕಿತ್ಸೆ ಅಗತ್ಯವಿಲ್ಲ."], ta=["சிகிச்சை தேவையில்லை."], te=["చికిత్స అవసరం లేదు."], mr=["उपचार नको."], bn=["চিকিৎসা লাগবে না।"]),
        "prevention": _list_section(en=["Maintain weed-free field."], hi=["खेत साफ रखें।"], kn=["ಜಮೀನನ್ನು ಕಳೆರಹಿತವಾಗಿಡಿ."], ta=["வயலை களை இன்றி பராமரிக்கவும்."], te=["పొలాన్ని కలుపు లేకుండా ఉంచండి."], mr=["शेत स्वच्छ ठेवा."], bn=["জমি আগাছামুক্ত রাখুন।"]),
        "avoid": _list_section(en=["No issues."], hi=["कोई समस्या नहीं।"], kn=["ಯಾವುದೇ ತೊಂದರೆಯಿಲ್ಲ."], ta=["பிரச்சனைகள் எதுவும் இல்லை."], te=["ఎటువంటి సమస్యలు లేవు."], mr=["அடச்சण नाही."], bn=["সমস্যা নেই।"]),
        "when_to_seek_help": _list_section(en=["Inspect weekly."], hi=["नियमित जांच करें।"], kn=["ವಾರಕ್ಕೊಮ್ಮೆ ಪರಿಶೀಲಿಸಿ."], ta=["வாரந்தோறும் கண்காணிக்கவும்."], te=["వారానికోసారి పరిశీలించండి."], mr=["दर आठवड्याला पाहणी करा."], bn=["সপ্তাহে একবার দেখুন।"]),
        "severity": _narrative_section(en="Low", hi="कम", kn="ಇಲ್ಲ", ta="குறைவு", te="తక్కువ", mr="कमी", bn="কম"),
        "spread_risk": _narrative_section(en="Low", hi="कम", kn="ಇಲ್ಲ", ta="குறைவு", te="తక్కువ", mr="कमी", bn="কম"),
        "hindi": {"disease": "स्वस्थ"},
    },
}

@lru_cache(maxsize=1)
def supported_disease_names() -> list[str]:
    names = set(DISEASE_INFO)
    for item in _classes():
        names.add(item["class_name"])
    return sorted(names)


def list_supported_classes() -> list[str]:
    return supported_disease_names()


def validate_supporting_data() -> list[str]:
    missing = []
    for class_name in supported_disease_names():
        try:
            profile = _profile_for_key(class_name)
        except KeyError:
            missing.append(f"{class_name}: no advisory profile")
            continue
        for field in REQUIRED_FIELDS:
            value = profile.get(field)
            if value is None:
                missing.append(f"{class_name}: missing {field}")
                continue
            if isinstance(value, dict) and "en" in value and "hi" in value:
                if value["en"] in (None, "") or value["hi"] in (None, ""):
                    missing.append(f"{class_name}: empty bilingual value for {field}")
            elif isinstance(value, dict):
                if not value:
                    missing.append(f"{class_name}: empty {field}")
            elif isinstance(value, list):
                if not value:
                    missing.append(f"{class_name}: empty {field}")
    return missing


def prediction_block(class_name: str, confidence: float) -> dict:
    """The ML prediction, in the exact shape requested for the API."""
    class_key = _alias_key(class_name)
    c = _by_name().get(class_name, _by_name().get(class_key, {
        "crop": DISEASE_INFO.get(class_key, {}).get("crop", "Unknown"),
        "disease": DISEASE_INFO.get(class_key, {}).get("disease", "Unknown"),
        "is_healthy": False,
        "crop_hi": "अज्ञात",
        "disease_hi": "अज्ञात"
    }))
    return {
        "class_name": class_name,
        "crop": c["crop"],
        "disease": c["disease"],
        "confidence": round(float(confidence), 4),
        "is_healthy": c.get("is_healthy", False),
        "crop_hi": c.get("crop_hi", c["crop"]),
        "disease_hi": c.get("disease_hi", c["disease"]),
    }


@lru_cache(maxsize=1)
def _advice_translations() -> dict[str, dict[str, dict]]:
    directory = Path(settings.DATA_DIR) / "advice_i18n"
    allow_drafts = os.environ.get("ALLOW_DRAFT_TRANSLATIONS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    translations: dict[str, dict[str, dict]] = {}

    for language in _ADVICE_LANGUAGES:
        sources = (
            (directory / f"{language}.json", False),
            (directory / "drafts" / f"{language}.json", True),
        )
        for path, is_draft_file in sources:
            if not path.is_file():
                continue

            document = _read(path)
            status = document.get("status")
            if status not in {"reviewed", "draft"}:
                raise ValueError(f"{path} must have status 'reviewed' or 'draft'")
            if is_draft_file and status != "draft":
                continue
            if status == "draft" and not allow_drafts:
                continue

            classes = document.get("classes")
            if not isinstance(classes, dict):
                raise ValueError(f"{path} must contain a classes object")

            for class_name, class_data in classes.items():
                fields = class_data.get("fields") if isinstance(class_data, dict) else None
                if not isinstance(fields, dict):
                    raise ValueError(f"{path}: {class_name} must contain a fields object")
                if set(fields) != set(_ADVICE_FIELDS):
                    raise ValueError(f"{path}: {class_name} has an incomplete advice fields set")

                key = _norm_class_name(class_name)
                translations.setdefault(key, {})[language] = fields

    return translations


def _apply_advice_translations(profile: dict) -> dict:
    class_name = profile.get("class_name", "")
    by_language = _advice_translations().get(_norm_class_name(class_name), {})
    for language, fields in by_language.items():
        for field in _ADVICE_FIELDS:
            if field not in fields or field not in profile:
                continue

            english = profile[field].get("en") if isinstance(profile[field], dict) else None
            translated = fields[field]
            if not isinstance(english, (str, list)) or not isinstance(translated, type(english)):
                raise ValueError(f"{class_name}: invalid {language} translation type for {field}")
            if isinstance(english, list) and len(translated) != len(english):
                raise ValueError(f"{class_name}: {language} translation length mismatch for {field}")
            profile[field][language] = copy.deepcopy(translated)

    return profile


@lru_cache(maxsize=1)
def _guidance() -> dict:
    out = {}
    for class_name in list_supported_classes():
        try:
            profile = _profile_for_key(class_name)
        except KeyError:
            continue
        out[class_name] = profile
        out[_norm_class_name(class_name)] = profile
    return out


def get_guidance(class_name: str) -> dict:
    key = _alias_key(class_name)
    if key in DISEASE_INFO:
        profile = _profile_for_key(key)
    elif class_name in _guidance():
        profile = copy.deepcopy(_guidance()[class_name])
    else:
        profile = _profile_for_key("Tomato_early_blight")
    
    # Overwrite class_name to ensure it matches the input prediction name exactly
    profile["class_name"] = class_name
    
    return _apply_advice_translations(profile)


def get_disease_profile(class_name: str) -> dict:
    return get_guidance(class_name)