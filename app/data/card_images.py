"""
Маппинг персонаж → путь к изображению карточки.
Пути относительно корня проекта (images/card/<rank>/<file>.png).
"""
import json
import pathlib

# ── Маппинг: имя персонажа (как в CHARACTERS) → относительный путь ────────────
CARD_IMAGE_MAP: dict[str, str] = {

    # ── new_legend ────────────────────────────────────────────────────────────
    "Og Daniel (UI)":         "images/card/new_legend/OGDaniel_UI.png",
    "Gun (Mastery)":          "images/card/new_legend/Gun_Mastery.png",
    "Go (Katana)":            "images/card/new_legend/Goo_Katana.png",
    "Johan (PB copy + Path)": "images/card/new_legend/Johan_BPCopyPath.png",
    "Johan (Path)":           "images/card/new_legend/Johan_Path.png",
    "Johan (PB copy)":        "images/card/new_legend/Johan_PBCopy.png",
    "Gun (Base)":             "images/card/new_legend/Gun_Base.png",
    "Goo (Weapon)":           "images/card/new_legend/Goo_Weapon.png",
    "Og Daniel (Path)":       "images/card/new_legend/OGDaniel_Path.png",
    "Johan (Eye drops)":      "images/card/new_legend/Johan_Eyedrops.png",
    "Jake (Overcoming)":      "images/card/new_legend/Jake_Overcoming.png",
    "Samuel (Hormones)":      "images/card/new_legend/Samuel_Hormones.png",

    # ── legend ────────────────────────────────────────────────────────────────
    "Tom (Rage mode)":       "images/card/legend/TomLee_RageMode.png",
    "Gapryong (Overcoming)": "images/card/legend/Gapryong_Overcoming.png",
    "Gun (TUI)":             "images/card/legend/Gun_TUI.png",
    "Goo (Hwarang)":         "images/card/legend/Goo_Hwarang.png",
    "Big Danuel (UI)":       "images/card/legend/BigDaniel_UI.png",
    "Jincheol (Path)":       "images/card/legend/Jincheol_Path.png",
    "Sophia (Path)":         "images/card/legend/Sophia_Path.png",
    "Samdak (Prime)":        "images/card/legend/Samdak_Prime.png",
    "Meneger Kim (Path)":    "images/card/legend/ManagerKim_Path.png",
    "Hansu (0%)":            "images/card/legend/Hansu_0%.png",
    "Goo (50 styles)":       "images/card/legend/Goo_50Styles.png",
    "Brekdak (Legend)":      "images/card/legend/Brekdak_Legend.png",

    # ── peak ──────────────────────────────────────────────────────────────────
    "Daniel (Prime)":    "images/card/peak/Daniel_Prime.png",
    "Gapryong (Prime)":  "images/card/peak/Gapryong_Prime.png",
    "Shingen (Prime)":   "images/card/peak/Shinghen_Prime.png",
    "James (Prime)":     "images/card/peak/James_Prime.png",
    "Gitae (Path)":      "images/card/peak/Gitae_Path.png",
    "Mujin (Prime)":     "images/card/peak/Mujin_Prime.png",
    "Jinyoung (Path)":   "images/card/peak/Junyong_Path.png",  # Junyong = Jinyoung (준영)

    # ── member ────────────────────────────────────────────────────────────────
    "Arim (Crewhead)":      "images/card/member/Arim_Crewhead.png",
    "Jinoon (Crewhead)":    "images/card/member/Jihoon_Crewhead.png",
    "Sanggjin (Crewhead)":  "images/card/member/Sangjin_Crewhead.png",
    "Crystal":              "images/card/member/Crystal.png",
    "Mary":                 "images/card/member/Mary.png",
    "Sally Park":           "images/card/member/SallyPark.png",
    "Logan (Hostel B)":     "images/card/member/Logan_HostelB.png",
    "Roy (Speed 2)":        "images/card/member/Roy_Speed2.png",
    "Sung (Speed 2)":       "images/card/member/Sung_Speed2.png",
    "Yeowool (Speed 3)":    "images/card/member/Yeowool_Speed3.png",
    "Boknam (Speed 4)":     "images/card/member/Boknam_Speed4.png",
    "Sebastian (Speed 5)":  "images/card/member/Sebastian_Speed5.png",
    "Mira":                 "images/card/member/Mira.png",
    "Zoe":                  "images/card/member/Zoe.png",

    # ── boss ──────────────────────────────────────────────────────────────────
    "Kenta (2 Mastery)":   "images/card/boss/Kenta_2Mastery.png",
    "Hudson (Mastery)":    "images/card/boss/Hudson_Mastery.png",
    "Vin jin (Base)":      "images/card/boss/VinJin_Base.png",
    "Yuseong (Base)":      "images/card/boss/Yuseong_Base.png",
    "Ryuhei (Base)":       "images/card/boss/Ryuhei_Base.png",
    "Vasko (Base)":        "images/card/boss/Vasco_Base.png",
    "Jinchang (Crewhead)": "images/card/boss/Jinchang_Crewhead.png",
    "Olli (Hostel B)":     "images/card/boss/Olli_HostealB.png",
    "Jihan (Prime)":       "images/card/boss/Jihan_Prime.png",
    "Jibeom (Prime)":      "images/card/boss/Jibeom_Prime.png",
    "Xiaolung (Staff)":    "images/card/boss/Xiaolung_Staff.png",
    "Mitsuki":             "images/card/boss/Mitsuki.png",

    # ── king ──────────────────────────────────────────────────────────────────
    "Dalyoung (King busan)":  "images/card/king/Dalyoung_KingBusan.png",
    "NO 1 (Full power)":      "images/card/king/N1_FullPower.png",
    "Jake (Base)":            "images/card/king/Jake_Base.png",
    "Samuel (Base)":          "images/card/king/Samuel_Base.png",
    "Gongseob (One step)":    "images/card/king/Gongseob_OneStep.png",
    "Zack (Base)":            "images/card/king/Zack_Base.png",
    "Big Danuel (Base)":      "images/card/king/BigDaniel_Base.png",
    "Sang (No 2 Busan)":      "images/card/king/Sang_No2Busan.png",
    "Og Danuel (Base)":       "images/card/king/OGDaniel_Base.png",
    "Taesoo (Ultimate fist)": "images/card/king/Taesoo_UltimateFist.png",
    "Taehun (Principles)":    "images/card/king/Taehun_Principles.png",
    "Jonah (Drugged)":        "images/card/king/Johan_Drugged.png",
    "Sinu (Current)":         "images/card/king/Sinu_Current.png",
    "Eli (Base)":             "images/card/king/Eli_Base.png",
    "Gongseob (One gen)":     "images/card/king/Gongseob_OneGeneration.png",
    "Taesoo (One gen)":       "images/card/king/Taesoo_OneGen.png",
    "Seokdu (Prime)":         "images/card/king/Seokdu_Prime.png",
    "Taejin (Kudo)":          "images/card/king/Taejin_Kudo.png",
    "Vin jin (Kudo)":         "images/card/king/VinJin_Kudo.png",
    "Vasco (Hero)":           "images/card/king/Vasko_Hero.png",
    "Jay (Weapon)":           "images/card/king/Jay_Weapons.png",
    "Warren (CQC)":           "images/card/king/Warren_Cqc.png",
    "Jerry (Boxing)":         "images/card/king/Jerry_Boxing.png",
    "Jungseok (No 3 Busan)":  "images/card/king/Jungseok_No3Busan.png",
    "Baekjin (No 4 Busan)":   "images/card/king/Baekjin_No4Busan.png",
    "Jaegwang (No 5 Busan)":  "images/card/king/Jaegwang_No5Busan.png",
    "Hashik (No 6 Busan)":    "images/card/king/Hashik_No6Busan.png",
    "BJ Showby (Bucheon)":    "images/card/king/BJShowby_Buchron.png",
    "Junyuk (Uijeongbu)":     "images/card/king/Junyuk_Uijeonbu.png",
    "Jaemin (Daejeon)":       "images/card/king/Jaemin_Daegeon.png",

    # ── strong_king ───────────────────────────────────────────────────────────
    "Gitae (Base)":              "images/card/strong_king/Gitae_Base.png",
    "Jinrang (Overcoming)":      "images/card/strong_king/Jinrang_Overcoming.png",
    "James (3 Mastery)":         "images/card/strong_king/James_3Mastery.png",
    "Seongji (3 Mastery)":       "images/card/strong_king/Soengji_3Mastery.png",
    "Changsu (4 Mastery)":       "images/card/strong_king/Changsu_4Mastery.png",
    "J (Police)":                "images/card/strong_king/Jay_Police.png",
    "Jaegyeon (3 Mastery)":      "images/card/strong_king/Jaegyeon_3Mastery.png",
    "Yujae (3 Mastery)":         "images/card/strong_king/Yujae_3Mastery.png",
    "Yugang (Legend incheon)":   "images/card/strong_king/Yugang_LenengIncheon.png",
    "Jaegyeon (King incheon)":   "images/card/strong_king/Jaegyon_KingIncheon.png",
    "Yujae (Dark society)":      "images/card/strong_king/Yujae_DarkSociety.png",
    "James (2 Mastery)":         "images/card/strong_king/James_2Mastery.png",
    "Seongji (2 Mastery)":       "images/card/strong_king/Soengji_2Mastery.png",
    "Jinrang (Conviction)":      "images/card/strong_king/Jinrang_Conviction.png",
    "Jinrang (Base)":            "images/card/strong_king/Jinrang_Base.png",
    "Jinchang (Prime)":          "images/card/strong_king/Jinchang_Prime.png",
    "Og Daniel (Copy)":          "images/card/strong_king/OGDaniel_Copy.png",
    "Ryu (Dark society)":        "images/card/strong_king/Ryu_DarkSociety.png",
    "Mugak (Dark society)":      "images/card/strong_king/Mugak_DarkSociety.png",
    "Jake (Awaking)":            "images/card/strong_king/Jake_Awaking.png",
    "Samuel (Drugged)":          "images/card/strong_king/Samuel_Drugged.png",
    "Yuseong (Crying)":          "images/card/strong_king/Yuseong_Crying.png",
    "Big Daniel (Copy)":         "images/card/strong_king/BigDaniel_Copy.png",
    "Lineman (Hidden dragon)":   "images/card/strong_king/Lineman_HiddenDragon.png",
    "Zack (Mastery)":            "images/card/strong_king/Zack_Mastery.png",
    "Eli (Wildness)":            "images/card/strong_king/Eli_Savageness.png",
    "Mandeok (Mastery)":         "images/card/strong_king/Maeondok_Mastery.png",
    "Ryuhei (Kagiroi)":          "images/card/strong_king/Ryuhei_Kagiroi.png",

    # ── gen_zero ──────────────────────────────────────────────────────────────
    "Old Gapryong (Overcoming)": "images/card/gen_zero/OldGapryong_Overcoming.png",
    "Shingen (TUI Lethargic)":   "images/card/gen_zero/Shinghen_LethargicTui.png",
    "Baekho (Prime)":            "images/card/gen_zero/Baekho_Prime.png",
    "Old Gapryong (Base)":       "images/card/gen_zero/OldGapryong_Base.png",
    "Shingen (Lethargic)":       "images/card/gen_zero/Shinghen_Lethargic.png",
    "Tom (Wildness)":            "images/card/gen_zero/TomLee_Wildness.png",
    "Jinyoung (Prime)":          "images/card/gen_zero/Jinyoung_Prime.png",
    "Shintaro (Muramasa)":       "images/card/gen_zero/Shintaro_Murasama.png",
    "Elite (Prime)":             "images/card/gen_zero/Elite_Prime.png",
    "Shintaro (UI)":             "images/card/gen_zero/Shintaro_UI.png",
    "Jinyoung (Old)":            "images/card/gen_zero/Jinyoung_Old.png",
    "Tom (Base)":                "images/card/gen_zero/TomLee_Base.png",
    "Paecheon (Hwarang)":        "images/card/gen_zero/Paecheon_Hwarang.png",
    "Paecheon (Dark blood)":     "images/card/gen_zero/Paecheon_DarkBlood.png",
    "Elite (Old)":               "images/card/gen_zero/Elite_OId.png",
    "Gentleman (Prime)":         "images/card/gen_zero/Gentleman_Prime.png",
    "Choi (Lighting)":           "images/card/gen_zero/Choi_Lighting.png",
    "Paecheon (Base)":           "images/card/gen_zero/Paecheon_Base.png",
    "Shigeaki (Kojima)":         "images/card/gen_zero/Shigeaki_Kojima.png",
    "Hiroaki (Kojima)":          "images/card/gen_zero/Hiroaki_Kojima.png",
    "Jaesu (Prime)":             "images/card/gen_zero/Jaesu_Prime.png",
    "Beolgu (Prime)":            "images/card/gen_zero/Beolgu_Prime.png",
    "Gwang (Prime)":             "images/card/gen_zero/Gwang_Prime.png",
    "Bakgu (NOH)":               "images/card/gen_zero/Bakgu_NON.png",  # filename typo: NON → NOH
    "Somi (Mom Gun)":            "images/card/gen_zero/Somi _GunMom.png",
    "Ms'Kim":                    "images/card/gen_zero/Ms'Kim.png",

    # ── absolute ──────────────────────────────────────────────────────────────
    "Kuropatkaa (Hopeful)":         "images/card/absolute/Kuropatkaa_Hopeful.png",
    "Marise (Boosty)":              "images/card/absolute/Marise_Boosty.png",
    "Some Thing (STYLIST)":         "images/card/absolute/SomeThing_Stylist.png",
    "Архангел (WWIP)":              "images/card/absolute/Arhangel_WWIP.png",
    "Никита (Despair)":             "images/card/absolute/Nikita_Despair.png",
    "Менеджер (Fair)":              "images/card/absolute/Meneger_Fair.png",
    "Quan'de Manchesten (100M)":    "images/card/absolute/QuandeManchester_100M.png",
    "Malosolny Ogurchik (Emperor)": "images/card/absolute/MolosolnyOgurchik_Emperor.png",
    "Табаско (Unlucky)":            "images/card/absolute/Tabasko_Unlucky.png",
    "Arian (Absolute)":             "images/card/absolute/Ariam_Absolute.png",

    # ── perfection ────────────────────────────────────────────────────────────
    "Братья (СЧ и НХ)":            "images/card/perfection/Brother.png",
    "Менеджер (Жмот (Prime))":      "images/card/perfection/Meneger_Prime.png",
    "Communists (Clan)":            "images/card/perfection/Communists_Clan.png",
}

# ── Кэш file_id (персистентный через JSON) ────────────────────────────────────
_CACHE_FILE = pathlib.Path("data/card_file_ids.json")
_file_id_cache: dict[str, str] = {}


def _load_cache() -> None:
    global _file_id_cache
    if _CACHE_FILE.exists():
        try:
            _file_id_cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _file_id_cache = {}


def _save_cache() -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(_file_id_cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


_load_cache()


def get_image_path(char_name: str) -> str | None:
    """Возвращает относительный путь к изображению или None."""
    return CARD_IMAGE_MAP.get(char_name)


def get_cached_file_id(char_name: str) -> str | None:
    """Возвращает кэшированный Telegram file_id или None."""
    return _file_id_cache.get(char_name)


def cache_file_id(char_name: str, file_id: str) -> None:
    """Сохраняет file_id в память и на диск."""
    _file_id_cache[char_name] = file_id
    _save_cache()
