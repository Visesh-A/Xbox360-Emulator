"""The strings createprofile.xex shows while creating a profile, straight from
the console's string tables (createprofile.txt, one "<key> <text>" per line,
\\n escaped):
  title        CreateProfile_Custom.xus 12 (keyboard title, error box title)
  prompt       LiveProfile.xus 6 (keyboard description)
  err_dup      LiveProfile.xus 7 (%s = the name)
  err_end      LiveProfile.xus 8      err_chars  LiveProfile.xus 9
  err_letter   LiveProfile.xus 10     err_empty  LiveProfile.xus 11
  err_spaces   LiveProfile.xus 12
  ok           LiveAll.xus 16 (the error box's button)
  invalid      LiveAll.xus 10 (fallback error, %s = the name)
  cant_title   CreateProfile_Custom.xus 17 ("Can't Connect", Join Xbox Live
  cant_text    CreateProfile_Custom.xus 16  offline: createprofile 901030D8,
  test         CreateProfile_Custom.xus 35  buttons Test Connection, Cancel)
  cancel       LiveAll.xus 0
  live_title   CreateProfile_Custom.xus 7   (Join Xbox Live the first time,
  live_text    CreateProfile_Custom.xus 6    90102D78: retail flags lack 0x4)
  live_yes     CreateProfile_Custom.xus 13   live_no  CreateProfile_Custom.xus 22
  exit_title   CreateProfile_Custom.xus 5   (Test Connection, 90102E60,
  exit_text    CreateProfile_Custom.xus 4    buttons Yes, No)
  yes          LiveAll.xus 17               no       LiveAll.xus 15
  st_*         AddXboxLive's status line (901022E0): st_creating #8,
               st_signing #29, st_updating #36, st_network #0
Validation order (createprofile 90107AD0, offline = LiveProfile index + 7):
empty, first char not a letter, a char not letter/digit/space, two spaces,
trailing space, name in use; the name is first collapsed (90105E40)."""
import make_guide_assets as G
import xui_render as X
import xus


def main():
    custom = xus.load(X.ART / "createprofile" / "CreateProfile_Custom.xus")
    profile = xus.load(X.ART / "shrdres" / "LiveProfile.xus")
    live = xus.load(X.ART / "shrdres" / "LiveAll.xus")
    entries = {
        "title": custom[12], "prompt": profile[6], "err_dup": profile[7],
        "err_end": profile[8], "err_chars": profile[9], "err_letter": profile[10],
        "err_empty": profile[11], "err_spaces": profile[12], "ok": live[16],
        "invalid": live[10], "cant_title": custom[17], "cant_text": custom[16],
        "test": custom[35], "cancel": live[0],
        "live_title": custom[7], "live_text": custom[6], "live_yes": custom[13],
        "live_no": custom[22], "exit_title": custom[5], "exit_text": custom[4],
        "yes": live[17], "no": live[15],
        "st_network": custom[0], "st_creating": custom[8], "st_signing": custom[29],
        "st_updating": custom[36],
    }
    lines = [f"{k} " + v.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n")
             for k, v in entries.items()]
    (G.OUT / "createprofile.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
