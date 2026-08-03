"""
Three.js job search visualizer.

This builder deliberately avoids Plotly. The old Plotly version coupled UI events
directly to trace indexes and frequent restyle calls; this version keeps one small
state object, a stable Three.js scene, delegated UI events, and synced map/list/3D
hover state.

Regenerate:
  python working/scripts/viz/build_job_viz_three.py

Output:
  working/active/job_search_viz.html
"""

from __future__ import annotations

import ast
import json
import math
import re
import shutil
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKING = ROOT / "working"
LEGACY = Path(__file__).with_name("build_job_viz.py")
OUT = WORKING / "active" / "job_search_viz.html"
NEXT = WORKING / "active" / "job_search_viz_next.html"
ARCHIVE = WORKING / "archive" / "viz"

# Sweep-coverage dataset (single source of truth in build_sweep_viz.py) — loaded
# by path so this works whether or not the viz dir is on sys.path.
import importlib.util as _ilu
_covspec = _ilu.spec_from_file_location("build_sweep_viz", Path(__file__).with_name("build_sweep_viz.py"))
_covmod = _ilu.module_from_spec(_covspec); _covspec.loader.exec_module(_covmod)
COV_SWEEPS, COV_FUTURE = _covmod.SWEEPS, _covmod.FUTURE

STATUS_ALIAS = {"File-ready": "Ready", "Canva-ported": "Ported"}
STATUS_COLORS = {
    "Applied": "#4f8fd8",
    "Interview": "#f0a13a",
    "Ready": "#a887ff",
    "Ported": "#44c7e8",
    "Queued": "#73c985",
    "Drafted": "#f47f55",
    "Target": "#27c6d8",
    "Declined": "#7f8795",
    "Closed": "#5c5350",
}

FIT_COLORS = ["#d85a4a", "#f28b58", "#e7c85d", "#73b4d4", "#3978bd"]

AXIS_LABELS = {
    "x": ["", "Startup", "Innovation org", "Nonprofit", "Post-secondary", "Gov"],
    "y": ["", "Ops", "Change mgmt", "Strategy", "Programs/Partnerships", "Ecosystem/R&D"],
    "z": ["", "Specialist", "Officer/Advisor", "Manager", "Director/ED", "VP/C-suite"],
}


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "job"


def load_legacy_jobs() -> list[dict]:
    """Read JOBS from the legacy builder without executing that builder."""
    tree = ast.parse(LEGACY.read_text(encoding="utf-8"))
    jobs_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "JOBS":
                    jobs_node = node.value
                    break
        if jobs_node is not None:
            break
    if jobs_node is None:
        raise RuntimeError(f"Could not find JOBS assignment in {LEGACY}")

    code = compile(ast.Expression(jobs_node), str(LEGACY), "eval")
    jobs = eval(code, {"__builtins__": {}, "dict": dict}, {})
    if not isinstance(jobs, list):
        raise TypeError("JOBS did not evaluate to a list")
    return jobs


# Region codes the map layer can draw. Anything else plots as Remote.
CA_PROVINCES = {
    "alberta": "AB", "british columbia": "BC", "manitoba": "MB",
    "new brunswick": "NB", "newfoundland and labrador": "NL",
    "newfoundland": "NL", "northwest territories": "NT", "nova scotia": "NS",
    "nunavut": "NU", "ontario": "ON", "prince edward island": "PE",
    "quebec": "QC", "québec": "QC", "saskatchewan": "SK", "yukon": "YT",
}
US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}
REGION_CODES = set(CA_PROVINCES.values()) | set(US_STATES.values())


def infer_location(job: dict) -> tuple[str, str]:
    """Resolve a job to (region code, display place).

    Set `loc` on each job — "Toronto, ON", "AB", "Remote". That is the only
    reliable input; the name scan below is a convenience for entries that
    predate the field, not a contract. An unrecognized region plots as Remote,
    which is a visible, correctable outcome rather than a silent mis-placement.
    """
    loc = str(job.get("loc") or "").strip()
    if loc:
        tail = loc.rsplit(",", 1)[-1].strip().upper()
        if tail in REGION_CODES:
            return tail, loc
        lowered = loc.lower()
        for names in (CA_PROVINCES, US_STATES):
            for name, code in names.items():
                if name in lowered:
                    return code, loc
        return "Remote", loc

    # No `loc`: scan the free text for a region name before giving up.
    text = f"{job.get('label','')} {job.get('org','')} {job.get('note','')}".lower()
    for names in (CA_PROVINCES, US_STATES):
        for name, code in names.items():
            if name in text:
                return code, name.title()
    return "Remote", job.get("org") or "Remote"


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    province_counts: dict[str, int] = {}
    for index, source in enumerate(jobs):
        job = dict(source)
        job["status"] = STATUS_ALIAS.get(job.get("status"), job.get("status", "Applied"))
        job["id"] = f"{slugify(job.get('label','job'))}-{index:02d}"
        job["index"] = index
        job["fit"] = int(job.get("fit", 1))
        job["p"] = int(job.get("p", 0))
        job["sal"] = int(job.get("sal", 0))
        job["sal_min"] = int(job.get("sal_min", job["sal"]))
        job["sal_max"] = int(job.get("sal_max", job["sal"]))
        province, place = infer_location(job)
        province_counts[province] = province_counts.get(province, 0) + 1
        job["province"] = province
        job["place"] = place
        job["provinceOrdinal"] = province_counts[province]
        enriched.append(job)
    return enriched


def backup_existing() -> None:
    if not OUT.exists():
        return
    text = OUT.read_text(encoding="utf-8", errors="ignore")
    if "Plotly.newPlot" not in text:
        return
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    target = ARCHIVE / f"job_search_viz_plotly_backup_{stamp}.html"
    if not target.exists():
        shutil.copy2(OUT, target)


def job_center(jobs: list[dict]) -> dict:
    return {
        "x": round(sum(j["x"] for j in jobs) / len(jobs), 3),
        "y": round(sum(j["y"] for j in jobs) / len(jobs), 3),
        "z": round(sum(j["z"] for j in jobs) / len(jobs), 3),
    }


# ── US state geometry ───────────────────────────────────────────────────────
# Same EHT equirectangular projection the Canada province paths use. The
# continental US lands at y ~= 420..1170 in this projection, so the combined
# North-America viewBox is "0 0 1608 1180" for the tier-2 US view.
CANADA_PROJ = {
    "minLng": -138.938599,
    "maxLat": 62.59193,
    "xscale": 18.3548,
    "scale": 29.9827,
    "pad": 12,
}

# Simplified contiguous-state outlines as [lng, lat] vertex rings (8-20 pts).
# Approximate — chosen for correct overall shape and geographic position, not
# census precision. Lng west-negative, lat north-positive.
US_STATE_OUTLINES_REAL = [
    dict(abr='AL',name='Alabama',d='M 956.3,977.9 L 953.9,981.3 L 946.9,982.3 L 950.8,980.4 L 946.8,968.4 L 944.5,978.2 L 939.6,978.1 L 938.0,932.5 L 945.4,841.3 L 943.2,838.6 L 990.6,839.3 L 1003.5,920.7 L 999.8,932.8 L 1001.9,959.2 L 954.4,959.2 L 957.8,970.0 L 956.3,977.9 Z M 945.7,981.6 L 941.2,982.0 L 945.7,981.6 Z',cx=966.3,cy=914.0),
    dict(abr='AR',name='Arkansas',d='M 915.7,809.3 L 907.6,835.9 L 890.6,870.0 L 888.1,879.0 L 889.2,898.8 L 836.1,898.9 L 836.0,882.6 L 828.0,879.8 L 828.8,827.7 L 825.5,794.3 L 907.3,794.3 L 908.9,800.4 L 903.3,809.5 L 915.7,809.3 Z',cx=875.2,cy=847.4),
    dict(abr='AZ',name='Arizona',d='M 560.6,949.4 L 524.0,949.5 L 454.4,914.0 L 461.0,904.0 L 456.5,889.3 L 460.4,872.1 L 467.4,860.7 L 458.5,842.1 L 456.1,808.9 L 460.5,804.6 L 466.4,808.4 L 469.0,803.8 L 469.0,779.2 L 560.7,779.3 L 560.6,949.4 Z',cx=491.2,cy=854.9),
    dict(abr='CA',name='California',d='M 458.5,839.5 L 462.9,854.6 L 467.4,859.8 L 462.1,867.7 L 456.9,886.7 L 460.3,906.1 L 412.3,913.2 L 406.1,890.4 L 394.8,877.6 L 388.8,876.9 L 387.0,868.7 L 375.3,865.9 L 366.8,856.7 L 350.8,855.1 L 347.8,851.9 L 347.5,835.6 L 325.2,799.4 L 326.4,783.8 L 315.7,773.1 L 313.7,763.0 L 314.7,755.4 L 321.6,765.0 L 317.1,749.1 L 331.6,747.7 L 315.7,745.0 L 313.3,754.5 L 305.8,747.7 L 304.6,749.7 L 306.2,743.4 L 291.7,722.1 L 289.3,696.1 L 279.7,678.2 L 284.9,647.9 L 282.0,629.4 L 359.6,629.4 L 359.6,719.3 L 458.5,839.5 Z M 361.8,866.9 L 367.9,868.4 L 363.1,870.2 L 361.8,866.9 Z M 354.0,868.5 L 351.5,868.3 L 354.0,868.5 Z M 358.8,871.7 L 355.0,868.8 L 358.3,868.5 L 358.8,871.7 Z M 389.9,887.7 L 390.9,889.9 L 388.1,889.7 L 385.9,885.3 L 389.9,887.7 Z M 369.9,892.7 L 367.4,890.9 L 369.9,892.7 Z M 389.9,904.4 L 386.1,898.3 L 389.9,904.4 Z',cx=359.5,cy=777.5),
    dict(abr='CO',name='Colorado',d='M 560.7,779.3 L 560.7,659.4 L 689.5,659.4 L 689.8,779.3 L 560.7,779.3 Z',cx=632.3,cy=715.8),
    dict(abr='CT',name='Connecticut',d='M 1244.3,629.0 L 1243.5,649.3 L 1223.7,650.8 L 1210.7,659.6 L 1209.0,656.3 L 1213.4,652.8 L 1213.5,627.7 L 1244.3,629.0 Z',cx=1227.1,cy=640.0),
    dict(abr='DC',name='District of Columbia',d='M 1148.3,722.7 L 1148.1,719.0 L 1148.3,722.7 Z',cx=1148.2,cy=721.9),
    dict(abr='DE',name='Delaware',d='M 1184.9,735.7 L 1172.6,735.7 L 1171.2,697.7 L 1173.9,694.2 L 1177.9,694.9 L 1175.0,705.0 L 1184.0,726.0 L 1182.1,731.6 L 1184.9,735.7 Z',cx=1176.5,cy=719.6),
    dict(abr='FL',name='Florida',d='M 956.3,977.9 L 957.8,970.0 L 954.4,959.2 L 1001.9,959.2 L 1004.2,967.6 L 1052.7,972.2 L 1055.0,978.1 L 1057.9,964.8 L 1066.2,967.3 L 1073.5,1005.5 L 1084.2,1034.6 L 1085.4,1052.1 L 1082.7,1033.5 L 1081.1,1038.8 L 1078.4,1026.4 L 1080.1,1037.7 L 1092.9,1084.9 L 1091.5,1114.1 L 1084.9,1132.2 L 1073.4,1135.0 L 1073.0,1129.8 L 1076.5,1131.2 L 1068.8,1114.2 L 1062.3,1109.6 L 1057.9,1094.4 L 1060.2,1088.5 L 1056.4,1092.6 L 1056.9,1080.3 L 1051.8,1083.0 L 1044.0,1064.2 L 1049.6,1053.3 L 1044.7,1050.2 L 1045.9,1055.8 L 1043.5,1057.9 L 1041.6,1053.8 L 1045.1,1022.6 L 1026.0,991.4 L 1019.6,986.1 L 1014.7,987.3 L 1013.4,992.0 L 996.2,998.8 L 995.5,992.9 L 989.6,985.5 L 991.0,980.6 L 987.5,984.0 L 975.3,977.2 L 981.4,977.0 L 979.0,974.4 L 961.6,979.0 L 965.6,976.3 L 965.4,972.1 L 960.2,979.0 L 956.6,980.4 L 956.3,977.9 Z M 1003.7,999.9 L 999.9,1000.2 L 1006.9,997.2 L 1003.7,999.9 Z M 1090.4,1070.8 L 1085.8,1053.6 L 1090.4,1070.8 Z M 1055.6,1092.6 L 1054.0,1088.1 L 1055.6,1092.6 Z M 1056.4,1095.5 L 1053.4,1092.7 L 1056.4,1095.5 Z M 1086.8,1134.8 L 1083.1,1140.5 L 1087.4,1130.2 L 1086.8,1134.8 Z M 1074.6,1147.6 L 1076.7,1146.3 L 1074.6,1147.6 Z M 1069.3,1149.6 L 1067.7,1146.6 L 1069.3,1149.6 Z M 1065.0,1151.1 L 1065.1,1148.4 L 1065.0,1151.1 Z',cx=1032.9,cy=1023.0),
    dict(abr='GA',name='Georgia',d='M 1001.9,959.2 L 999.8,932.8 L 1003.5,920.7 L 990.6,839.3 L 1036.6,839.2 L 1032.2,848.0 L 1041.5,856.2 L 1046.3,868.7 L 1064.8,897.2 L 1073.0,923.8 L 1077.8,928.3 L 1073.4,932.9 L 1072.2,943.3 L 1068.5,948.6 L 1070.2,951.3 L 1067.3,953.2 L 1066.2,967.3 L 1057.9,964.8 L 1055.0,978.1 L 1052.7,972.2 L 1004.2,967.6 L 1001.9,959.2 Z M 1067.8,960.1 L 1066.9,967.4 L 1067.8,960.1 Z',cx=1038.5,cy=920.8),
    dict(abr='IA',name='Iowa',d='M 883.8,678.0 L 878.5,670.6 L 804.4,671.3 L 798.5,634.8 L 788.7,607.5 L 791.7,595.5 L 789.1,584.5 L 887.4,584.4 L 890.6,605.8 L 897.6,611.1 L 907.5,630.0 L 902.2,642.6 L 891.0,648.3 L 892.7,658.9 L 883.8,678.0 Z',cx=844.0,cy=629.7),
    dict(abr='ID',name='Idaho',d='M 414.0,419.7 L 432.1,419.7 L 432.1,449.4 L 438.2,459.1 L 438.3,466.1 L 455.9,487.4 L 463.6,489.7 L 460.0,522.2 L 464.3,524.8 L 469.9,518.7 L 473.4,521.4 L 479.6,542.3 L 485.5,546.5 L 490.8,557.5 L 502.2,552.6 L 515.6,553.1 L 518.0,547.1 L 523.9,554.5 L 523.9,629.4 L 414.4,629.4 L 416.3,563.5 L 411.0,556.4 L 424.3,520.2 L 417.1,510.7 L 414.0,497.6 L 414.0,419.7 Z',cx=462.4,cy=532.7),
    dict(abr='IL',name='Illinois',d='M 883.8,678.0 L 892.7,658.9 L 891.0,648.3 L 902.2,642.6 L 907.0,632.9 L 907.2,626.4 L 898.3,614.0 L 964.6,614.6 L 961.3,636.6 L 955.8,636.6 L 953.4,714.3 L 955.6,727.1 L 947.3,741.9 L 945.0,763.3 L 937.9,768.4 L 938.3,776.7 L 927.8,773.8 L 925.8,779.6 L 921.0,776.2 L 919.0,760.0 L 903.5,741.7 L 907.8,723.9 L 899.7,722.1 L 885.0,696.9 L 883.8,678.0 Z',cx=924.7,cy=708.5),
    dict(abr='IN',name='Indiana',d='M 946.2,755.7 L 947.3,741.9 L 955.8,725.0 L 953.4,714.3 L 955.8,636.6 L 1005.8,636.6 L 1005.7,724.8 L 998.9,728.6 L 994.6,727.4 L 983.3,749.8 L 977.0,744.0 L 972.7,753.1 L 967.7,750.0 L 962.7,755.2 L 954.5,750.7 L 953.5,754.3 L 949.3,751.9 L 946.2,755.7 Z',cx=970.7,cy=725.3),
    dict(abr='KS',name='Kansas',d='M 689.8,779.3 L 689.6,689.3 L 812.1,689.3 L 819.8,693.5 L 817.4,704.1 L 825.4,715.6 L 825.5,779.3 L 689.8,779.3 Z',cx=763.9,cy=732.0),
    dict(abr='KY',name='Kentucky',d='M 925.8,779.6 L 927.8,773.8 L 938.3,776.7 L 937.9,768.4 L 945.0,763.3 L 944.6,758.3 L 948.9,751.9 L 953.5,754.3 L 954.5,750.7 L 956.9,751.2 L 962.7,755.2 L 967.7,750.0 L 972.7,753.1 L 977.0,744.0 L 983.3,749.8 L 994.6,727.4 L 998.9,728.6 L 1005.7,724.8 L 1006.3,715.6 L 1012.5,716.6 L 1016.2,723.4 L 1026.1,729.9 L 1040.9,728.0 L 1046.3,736.7 L 1045.8,744.8 L 1049.9,754.5 L 1057.7,763.1 L 1036.0,786.4 L 1025.3,791.7 L 945.2,788.5 L 945.9,794.3 L 920.3,794.3 L 924.9,790.5 L 925.8,779.6 Z',cx=984.5,cy=756.9),
    dict(abr='LA',name='Louisiana',d='M 836.1,898.9 L 889.2,898.8 L 889.2,910.5 L 893.0,920.9 L 885.1,936.0 L 879.9,959.2 L 915.1,959.2 L 913.6,970.9 L 919.1,983.4 L 906.1,977.8 L 902.7,985.0 L 907.0,988.3 L 915.1,984.0 L 913.7,989.0 L 917.0,992.1 L 921.3,987.8 L 922.1,994.6 L 915.4,1000.6 L 928.3,1013.1 L 925.8,1018.7 L 924.3,1016.7 L 921.7,1019.7 L 920.5,1013.4 L 907.3,1003.1 L 907.8,1015.1 L 903.3,1010.3 L 896.5,1015.3 L 891.9,1013.4 L 886.6,1010.5 L 889.1,1009.6 L 887.3,1002.3 L 882.5,1002.5 L 875.5,994.1 L 868.8,1002.5 L 852.0,995.8 L 839.3,996.5 L 845.5,957.8 L 836.0,929.3 L 836.1,898.9 Z M 924.5,986.7 L 925.2,984.1 L 924.5,986.7 Z M 931.8,995.0 L 931.1,987.5 L 931.8,995.0 Z M 877.3,1004.2 L 873.4,1000.9 L 875.8,1000.0 L 877.3,1004.2 Z',cx=887.3,cy=970.8),
    dict(abr='MA',name='Massachusetts',d='M 1244.3,629.0 L 1213.5,627.7 L 1217.6,606.8 L 1252.9,608.3 L 1262.6,603.1 L 1266.1,610.7 L 1258.2,619.5 L 1263.8,622.5 L 1269.5,636.7 L 1277.3,634.6 L 1273.0,627.3 L 1275.4,627.1 L 1278.3,639.1 L 1265.3,643.4 L 1264.5,638.0 L 1255.9,644.7 L 1256.3,637.0 L 1252.7,635.5 L 1251.9,628.9 L 1244.3,629.0 Z M 1268.0,648.1 L 1262.1,648.6 L 1266.0,645.7 L 1268.0,648.1 Z M 1277.8,651.4 L 1273.1,650.8 L 1276.6,647.5 L 1277.8,651.4 Z',cx=1250.3,cy=624.0),
    dict(abr='MD',name='Maryland',d='M 1148.3,722.7 L 1148.1,719.0 L 1146.6,721.0 L 1140.0,716.0 L 1133.2,701.4 L 1128.7,699.0 L 1121.4,703.4 L 1116.2,700.6 L 1103.2,713.0 L 1103.4,697.7 L 1171.2,697.7 L 1172.6,735.7 L 1184.9,735.7 L 1178.7,748.6 L 1170.0,750.2 L 1169.8,738.5 L 1166.3,741.0 L 1161.8,734.5 L 1162.4,731.3 L 1167.2,731.3 L 1163.3,726.6 L 1161.0,728.1 L 1164.1,723.8 L 1161.2,720.8 L 1164.7,716.9 L 1164.4,709.9 L 1169.5,708.1 L 1167.2,707.0 L 1168.0,701.8 L 1162.2,709.7 L 1161.2,707.2 L 1159.5,712.6 L 1156.8,711.3 L 1159.4,715.6 L 1157.0,717.4 L 1160.0,738.3 L 1155.0,733.2 L 1161.0,746.7 L 1151.3,737.6 L 1150.9,740.6 L 1148.8,736.0 L 1144.6,737.1 L 1148.3,722.7 Z M 1181.4,748.1 L 1183.8,740.4 L 1181.4,748.1 Z',cx=1154.1,cy=721.1),
    dict(abr='ME',name='Maine',d='M 1294.7,470.7 L 1298.9,473.4 L 1309.7,469.1 L 1317.6,477.0 L 1317.7,517.6 L 1324.5,521.4 L 1323.7,531.2 L 1330.1,534.4 L 1332.7,544.6 L 1328.9,549.2 L 1317.0,552.2 L 1313.0,557.9 L 1311.3,554.4 L 1305.8,554.2 L 1304.3,561.7 L 1299.2,559.3 L 1300.1,552.3 L 1291.6,569.8 L 1286.2,572.5 L 1285.5,570.0 L 1284.3,573.0 L 1283.7,569.6 L 1280.9,576.3 L 1278.0,573.8 L 1274.1,576.4 L 1263.9,597.3 L 1259.6,585.7 L 1257.4,530.6 L 1261.5,531.3 L 1269.6,517.3 L 1277.2,488.2 L 1289.1,469.0 L 1291.3,465.6 L 1294.8,466.7 L 1294.7,470.7 Z M 1310.6,559.5 L 1306.5,560.6 L 1308.6,555.7 L 1310.6,559.5 Z M 1302.6,563.6 L 1301.6,561.8 L 1302.6,563.6 Z',cx=1295.2,cy=536.0),
    dict(abr='MI',name='Michigan',d='M 919.5,449.6 L 935.7,441.6 L 944.0,442.7 L 1004.3,482.5 L 1010.1,495.8 L 1017.6,493.2 L 1020.8,506.9 L 1027.4,506.0 L 1030.1,509.6 L 1027.9,515.0 L 1047.0,529.0 L 1054.6,582.3 L 1047.1,610.7 L 1037.4,620.4 L 1036.5,630.9 L 1030.2,637.2 L 961.3,636.6 L 964.6,614.6 L 962.5,589.6 L 964.7,566.7 L 970.6,544.1 L 978.8,532.7 L 969.5,525.9 L 963.2,525.9 L 956.9,537.4 L 953.3,535.8 L 953.1,528.3 L 949.3,527.9 L 950.5,518.9 L 944.2,511.1 L 908.1,499.2 L 903.1,493.0 L 919.5,449.6 Z',cx=975.7,cy=527.9),
    dict(abr='MN',name='Minnesota',d='M 777.6,419.7 L 815.5,419.8 L 815.6,408.4 L 819.6,409.0 L 825.4,427.2 L 842.2,433.8 L 855.3,431.2 L 864.4,436.5 L 865.9,441.2 L 873.5,440.5 L 882.4,447.8 L 893.4,443.2 L 896.6,446.4 L 908.6,446.0 L 912.1,449.6 L 919.5,449.6 L 911.0,470.9 L 898.3,470.2 L 868.2,489.7 L 868.2,506.9 L 860.8,512.2 L 857.1,519.7 L 861.0,526.5 L 859.4,547.7 L 884.9,569.7 L 887.4,584.4 L 791.8,584.4 L 791.8,530.5 L 784.5,520.7 L 788.8,515.5 L 789.8,505.3 L 777.6,419.7 Z',cx=842.2,cy=489.9),
    dict(abr='MO',name='Missouri',d='M 915.7,809.3 L 903.3,809.5 L 908.9,800.4 L 907.3,794.3 L 825.5,794.3 L 825.4,715.6 L 817.4,704.1 L 819.8,693.5 L 811.8,689.1 L 804.4,671.3 L 878.5,670.6 L 883.8,678.0 L 885.0,696.9 L 899.7,722.1 L 907.8,723.9 L 903.5,741.7 L 919.0,760.0 L 919.7,772.9 L 925.8,779.6 L 924.9,790.5 L 920.0,794.6 L 918.5,792.7 L 915.7,809.3 Z',cx=877.7,cy=748.5),
    dict(abr='MS',name='Mississippi',d='M 943.8,839.3 L 938.0,932.5 L 939.6,978.1 L 930.4,976.7 L 922.7,978.8 L 919.1,983.4 L 913.6,970.9 L 915.1,959.2 L 879.9,959.2 L 885.1,936.0 L 893.0,920.9 L 889.2,910.5 L 888.1,879.0 L 904.9,839.2 L 943.8,839.3 Z M 936.7,982.7 L 933.7,981.3 L 936.7,982.7 Z',cx=907.6,cy=909.4),
    dict(abr='MT',name='Montana',d='M 468.6,419.7 L 652.7,419.7 L 653.2,539.4 L 523.9,539.4 L 523.9,554.5 L 518.0,547.1 L 515.6,553.1 L 502.2,552.6 L 489.7,556.9 L 485.5,546.5 L 479.6,542.3 L 473.4,521.4 L 469.9,518.7 L 464.3,524.8 L 460.0,522.2 L 463.6,489.7 L 455.9,487.4 L 438.5,466.4 L 438.2,459.1 L 432.1,449.4 L 432.1,419.7 L 468.6,419.7 Z',cx=520.2,cy=503.9),
    dict(abr='NC',name='North Carolina',d='M 1036.6,839.2 L 1014.4,839.6 L 1015.6,831.8 L 1044.2,808.4 L 1046.9,810.2 L 1051.7,805.3 L 1056.2,805.6 L 1062.0,798.6 L 1063.4,791.0 L 1167.8,792.8 L 1170.5,805.9 L 1164.5,800.9 L 1164.5,804.9 L 1162.3,803.6 L 1163.1,805.8 L 1157.0,808.8 L 1153.8,802.4 L 1153.9,810.6 L 1165.9,810.2 L 1165.7,818.6 L 1170.7,810.6 L 1171.4,819.9 L 1164.0,828.7 L 1158.2,827.4 L 1156.6,823.3 L 1153.6,826.3 L 1148.1,823.5 L 1157.8,831.2 L 1152.9,839.6 L 1147.6,834.6 L 1149.3,838.5 L 1160.6,841.2 L 1153.8,848.1 L 1146.4,848.0 L 1143.4,851.2 L 1141.3,847.4 L 1141.9,853.5 L 1135.1,860.7 L 1131.8,871.1 L 1131.4,864.2 L 1130.3,871.9 L 1120.2,873.0 L 1100.2,845.4 L 1079.4,844.4 L 1073.8,834.6 L 1049.9,833.0 L 1036.6,839.2 Z M 1169.3,792.8 L 1175.8,814.7 L 1169.3,792.8 Z M 1173.9,813.6 L 1172.4,810.9 L 1173.9,813.6 Z M 1175.6,832.1 L 1172.9,832.6 L 1175.7,830.9 L 1176.3,816.2 L 1175.6,832.1 Z M 1171.2,833.6 L 1167.5,835.6 L 1171.2,833.6 Z M 1158.0,850.0 L 1163.4,841.1 L 1158.0,850.0 Z M 1157.2,849.6 L 1154.9,848.3 L 1157.2,849.6 Z',cx=1110.9,cy=825.4),
    dict(abr='ND',name='North Dakota',d='M 701.6,419.7 L 777.6,419.7 L 789.9,511.2 L 653.1,511.2 L 652.7,419.7 L 701.6,419.7 Z',cx=727.3,cy=473.1),
    dict(abr='NE',name='Nebraska',d='M 689.6,689.3 L 689.5,659.4 L 652.9,659.4 L 652.8,599.4 L 755.3,599.4 L 764.1,605.2 L 777.4,603.6 L 791.9,614.2 L 802.1,649.9 L 802.7,667.0 L 812.1,689.3 L 689.6,689.3 Z',cx=748.0,cy=650.8),
    dict(abr='NH',name='New Hampshire',d='M 1249.5,539.2 L 1253.0,530.8 L 1257.4,530.6 L 1259.6,585.7 L 1263.1,601.2 L 1252.9,608.3 L 1232.1,607.5 L 1234.0,581.8 L 1240.1,560.4 L 1247.8,554.0 L 1249.5,539.2 Z',cx=1248.5,cy=574.4),
    dict(abr='NJ',name='New Jersey',d='M 1184.2,689.9 L 1190.4,684.7 L 1182.1,671.5 L 1183.3,659.4 L 1191.1,648.7 L 1205.6,659.6 L 1199.1,673.5 L 1204.4,677.4 L 1202.5,695.7 L 1202.2,690.1 L 1196.1,707.7 L 1187.0,721.1 L 1187.5,715.0 L 1176.0,704.7 L 1177.8,695.7 L 1184.2,689.9 Z M 1201.5,698.9 L 1199.3,703.5 L 1201.5,698.9 Z',cx=1192.0,cy=684.0),
    dict(abr='NM',name='New Mexico',d='M 560.6,949.4 L 560.7,779.3 L 671.6,779.3 L 670.4,929.1 L 604.3,929.2 L 608.4,936.2 L 576.0,935.8 L 575.9,949.3 L 560.6,949.4 Z',cx=616.1,cy=873.5),
    dict(abr='NV',name='Nevada',d='M 469.0,779.2 L 469.0,803.8 L 466.4,808.4 L 460.5,804.6 L 456.1,808.9 L 458.5,839.5 L 359.6,719.3 L 359.6,629.4 L 469.0,629.4 L 469.0,779.2 Z',cx=431.4,cy=729.0),
    dict(abr='NY',name='New York',d='M 1098.2,613.2 L 1113.3,603.5 L 1109.0,585.4 L 1117.3,580.7 L 1152.2,580.6 L 1164.5,560.3 L 1182.3,542.5 L 1188.2,539.3 L 1215.8,539.3 L 1214.7,581.7 L 1217.8,582.8 L 1217.6,606.8 L 1213.0,627.0 L 1213.4,652.8 L 1204.2,666.8 L 1205.3,652.8 L 1205.6,659.6 L 1186.8,645.2 L 1183.8,634.4 L 1179.1,629.4 L 1098.2,629.4 L 1098.2,613.2 Z M 1231.3,659.8 L 1231.2,661.9 L 1242.4,657.6 L 1228.2,665.7 L 1203.7,671.9 L 1211.8,661.8 L 1229.2,659.6 L 1235.6,654.8 L 1231.3,659.8 Z M 1200.5,673.7 L 1202.7,669.9 L 1200.5,673.7 Z',cx=1175.6,cy=610.5),
    dict(abr='OH',name='Ohio',d='M 1036.5,630.9 L 1044.4,639.1 L 1049.0,639.1 L 1070.4,623.1 L 1084.2,619.7 L 1084.3,670.0 L 1077.8,699.4 L 1063.4,711.2 L 1061.1,720.9 L 1055.8,720.5 L 1053.4,731.2 L 1048.0,736.9 L 1040.9,728.0 L 1026.1,729.9 L 1016.2,723.4 L 1012.5,716.6 L 1005.3,716.6 L 1005.8,638.4 L 1030.2,637.2 L 1036.5,630.9 Z',cx=1051.2,cy=690.0),
    dict(abr='OK',name='Oklahoma',d='M 825.5,794.3 L 828.8,827.7 L 828.0,879.8 L 814.5,870.5 L 811.6,873.0 L 807.6,870.9 L 801.2,872.8 L 794.3,877.9 L 789.0,872.1 L 786.4,873.6 L 783.0,870.7 L 779.6,877.2 L 777.8,872.3 L 774.5,874.3 L 770.0,869.5 L 764.9,872.9 L 761.6,864.9 L 755.1,866.9 L 742.2,862.6 L 738.5,855.6 L 733.5,857.6 L 726.7,851.7 L 726.7,794.3 L 671.6,794.3 L 671.6,779.3 L 825.5,779.3 L 825.5,794.3 Z',cx=766.5,cy=836.5),
    dict(abr='OR',name='Oregon',d='M 359.6,629.4 L 282.0,629.4 L 279.7,625.7 L 276.3,605.0 L 283.5,578.7 L 286.4,502.9 L 303.8,504.7 L 309.6,519.3 L 319.2,521.7 L 329.1,517.9 L 340.4,520.3 L 353.2,517.7 L 377.6,509.5 L 416.6,509.4 L 423.5,517.8 L 411.0,556.4 L 416.3,563.5 L 414.4,629.4 L 359.6,629.4 Z',cx=345.4,cy=560.6),
    dict(abr='PA',name='Pennsylvania',d='M 1084.2,619.7 L 1098.2,613.2 L 1098.2,629.4 L 1179.1,629.4 L 1183.8,634.4 L 1185.9,644.2 L 1191.1,648.7 L 1183.3,659.4 L 1182.1,668.7 L 1190.4,684.7 L 1171.2,697.7 L 1084.3,697.7 L 1084.2,619.7 Z',cx=1138.8,cy=657.8),
    dict(abr='RI',name='Rhode Island',d='M 1243.5,649.3 L 1244.3,629.0 L 1251.9,628.9 L 1254.7,638.2 L 1251.8,635.5 L 1250.9,645.8 L 1243.5,649.3 Z M 1254.6,644.6 L 1254.7,639.8 L 1254.6,644.6 Z M 1252.3,644.8 L 1252.3,642.2 L 1252.3,644.8 Z',cx=1248.8,cy=637.6),
    dict(abr='SC',name='South Carolina',d='M 1077.8,928.3 L 1073.0,923.8 L 1064.8,897.2 L 1046.3,868.7 L 1041.5,856.2 L 1032.2,848.0 L 1036.5,839.3 L 1049.9,833.0 L 1073.8,834.6 L 1079.4,844.4 L 1100.2,845.4 L 1120.2,873.0 L 1113.6,879.5 L 1108.6,891.9 L 1108.0,887.1 L 1107.1,895.2 L 1097.4,905.6 L 1095.0,904.9 L 1094.9,909.2 L 1087.1,914.2 L 1082.2,913.9 L 1085.1,916.6 L 1083.2,920.6 L 1079.1,915.8 L 1081.1,922.8 L 1077.8,928.3 Z',cx=1076.4,cy=879.5),
    dict(abr='SD',name='South Dakota',d='M 791.8,584.4 L 789.1,584.5 L 791.7,595.5 L 788.6,606.7 L 791.3,614.1 L 777.4,603.6 L 764.1,605.2 L 755.3,599.4 L 652.8,599.4 L 653.1,511.2 L 789.9,511.2 L 784.5,520.7 L 791.8,530.5 L 791.8,584.4 Z',cx=737.2,cy=558.8),
    dict(abr='TN',name='Tennessee',d='M 990.6,839.3 L 904.9,839.2 L 916.0,811.7 L 918.4,794.3 L 945.9,794.3 L 945.2,788.5 L 1063.4,791.0 L 1062.0,798.6 L 1056.2,805.6 L 1051.7,805.3 L 1046.9,810.2 L 1044.2,808.4 L 1038.9,815.3 L 1022.7,823.8 L 1015.6,831.8 L 1014.4,839.6 L 990.6,839.3 Z',cx=977.9,cy=811.5),
    dict(abr='TX',name='Texas',d='M 828.0,879.8 L 836.0,882.6 L 836.0,929.3 L 845.5,957.8 L 842.2,985.8 L 838.8,998.5 L 822.9,1007.7 L 827.2,1002.7 L 822.6,1002.8 L 823.2,996.7 L 818.1,998.1 L 820.5,1008.1 L 813.5,1020.3 L 802.8,1030.0 L 795.8,1034.5 L 799.9,1030.2 L 791.9,1031.3 L 788.4,1027.9 L 792.4,1035.4 L 787.7,1038.9 L 785.9,1036.5 L 784.7,1043.3 L 778.9,1044.8 L 780.4,1049.6 L 773.9,1054.0 L 776.5,1059.0 L 773.7,1069.3 L 767.7,1065.4 L 769.1,1070.5 L 772.9,1072.0 L 773.8,1094.6 L 779.2,1108.2 L 774.9,1113.0 L 743.1,1095.7 L 736.7,1077.4 L 735.8,1062.7 L 721.3,1039.3 L 712.9,1013.7 L 701.4,996.9 L 683.7,993.2 L 676.5,999.9 L 670.0,1017.9 L 663.9,1017.1 L 645.9,1002.0 L 636.4,971.7 L 613.9,945.7 L 604.3,929.2 L 670.4,929.1 L 670.9,794.3 L 726.7,794.3 L 726.7,851.7 L 732.5,856.8 L 738.5,855.6 L 742.2,862.6 L 755.1,866.9 L 761.6,864.9 L 764.9,872.9 L 770.0,869.5 L 774.5,874.3 L 778.2,872.5 L 779.1,877.1 L 783.0,870.7 L 786.4,873.6 L 789.0,872.1 L 794.3,877.9 L 801.2,872.8 L 807.6,870.9 L 811.6,873.0 L 814.5,870.5 L 828.0,879.8 Z M 817.8,1014.8 L 822.7,1009.0 L 817.8,1014.8 Z M 786.1,1044.6 L 792.7,1037.7 L 786.1,1044.6 Z M 781.5,1052.1 L 784.4,1045.2 L 781.5,1052.1 Z M 775.3,1070.1 L 780.7,1054.5 L 775.3,1070.1 Z M 778.6,1104.3 L 774.7,1073.3 L 778.6,1104.3 Z',cx=753.1,cy=952.4),
    dict(abr='UT',name='Utah',d='M 560.7,779.3 L 469.0,779.2 L 469.0,629.4 L 523.9,629.4 L 523.9,659.4 L 560.7,659.4 L 560.7,779.3 Z',cx=507.7,cy=698.9),
    dict(abr='VA',name='Virginia',d='M 1146.6,721.0 L 1148.0,726.1 L 1143.1,737.4 L 1148.0,738.6 L 1162.4,752.5 L 1160.9,759.1 L 1158.2,758.9 L 1146.8,744.4 L 1161.6,762.2 L 1162.4,768.6 L 1159.9,767.7 L 1158.9,771.1 L 1153.3,764.2 L 1162.0,777.7 L 1159.9,779.6 L 1155.6,772.7 L 1144.3,769.4 L 1154.9,774.1 L 1158.3,782.4 L 1167.2,781.9 L 1169.8,792.8 L 1026.5,791.2 L 1036.0,786.4 L 1057.7,763.1 L 1059.4,769.4 L 1064.6,773.1 L 1069.0,769.3 L 1072.2,771.4 L 1087.0,765.1 L 1100.4,732.2 L 1107.8,735.0 L 1111.4,725.7 L 1119.8,719.4 L 1124.6,705.8 L 1133.5,715.0 L 1135.5,709.0 L 1139.1,711.4 L 1140.0,716.0 L 1146.6,721.0 Z M 1173.5,750.7 L 1178.7,748.6 L 1168.4,774.8 L 1167.7,767.4 L 1173.5,750.7 Z M 1180.9,748.2 L 1178.6,753.2 L 1180.9,748.2 Z',cx=1117.9,cy=758.6),
    dict(abr='VT',name='Vermont',d='M 1215.8,539.3 L 1249.5,539.2 L 1247.8,554.0 L 1240.1,560.4 L 1234.0,581.8 L 1232.1,607.5 L 1217.1,605.0 L 1217.8,582.8 L 1214.7,581.7 L 1215.8,539.3 Z',cx=1227.7,cy=574.4),
    dict(abr='WA',name='Washington',d='M 308.4,419.7 L 414.0,419.7 L 414.0,497.6 L 416.6,509.4 L 377.6,509.5 L 353.2,517.7 L 340.4,520.3 L 329.1,517.9 L 319.2,521.7 L 309.6,519.3 L 303.8,504.7 L 284.9,501.1 L 285.4,491.3 L 287.2,496.5 L 288.2,489.7 L 284.1,483.6 L 289.1,480.6 L 284.1,478.4 L 283.6,480.8 L 279.3,459.7 L 274.0,450.3 L 273.2,438.1 L 286.6,444.5 L 305.0,447.3 L 308.6,445.4 L 310.9,453.1 L 302.0,467.9 L 306.0,467.3 L 303.7,465.1 L 313.1,451.9 L 310.5,461.1 L 312.3,470.7 L 308.8,472.9 L 307.7,469.4 L 304.0,475.3 L 310.0,476.2 L 316.4,468.3 L 315.5,456.0 L 318.5,449.2 L 313.4,444.7 L 315.4,440.7 L 310.6,435.6 L 313.8,434.3 L 313.5,429.4 L 308.4,419.7 Z M 308.5,429.3 L 306.5,431.7 L 304.5,430.0 L 308.5,429.3 Z M 304.3,434.5 L 301.6,431.3 L 304.3,434.5 Z M 307.8,436.6 L 306.7,433.0 L 307.8,436.6 Z M 312.4,444.8 L 315.9,451.8 L 309.2,442.3 L 311.4,438.0 L 313.1,439.9 L 310.1,442.6 L 312.4,444.8 Z M 313.8,461.7 L 312.8,458.4 L 313.8,461.7 Z M 315.7,467.6 L 313.5,468.8 L 314.0,464.8 L 315.7,467.6 Z M 307.2,473.4 L 306.7,471.3 L 307.2,473.4 Z',cx=325.2,cy=466.7),
    dict(abr='WI',name='Wisconsin',d='M 898.3,614.0 L 889.7,603.0 L 886.0,571.3 L 859.4,547.7 L 861.0,526.5 L 857.1,519.7 L 860.8,512.2 L 868.2,506.9 L 868.2,489.7 L 898.3,470.2 L 911.0,470.9 L 902.7,491.9 L 908.1,499.2 L 944.2,511.1 L 950.5,518.9 L 949.3,527.9 L 953.1,528.3 L 953.3,535.8 L 956.9,537.4 L 963.2,525.9 L 969.5,525.9 L 978.8,532.7 L 970.6,544.1 L 964.7,566.7 L 962.5,589.6 L 964.6,614.6 L 898.3,614.0 Z',cx=909.5,cy=533.0),
    dict(abr='WV',name='West Virginia',d='M 1057.7,763.1 L 1052.0,758.7 L 1046.3,746.3 L 1045.8,735.9 L 1051.3,735.0 L 1055.8,720.5 L 1061.1,720.9 L 1063.4,711.2 L 1077.8,699.4 L 1082.1,671.3 L 1084.3,670.0 L 1084.3,697.7 L 1103.4,697.7 L 1103.2,713.0 L 1116.2,700.6 L 1120.0,703.4 L 1127.2,698.8 L 1133.2,701.4 L 1135.5,709.0 L 1133.5,715.0 L 1124.6,705.8 L 1119.8,719.4 L 1111.4,725.7 L 1107.8,735.0 L 1100.4,732.2 L 1087.0,765.1 L 1072.2,771.4 L 1069.0,769.3 L 1064.6,773.1 L 1059.4,769.4 L 1057.7,763.1 Z',cx=1088.6,cy=724.4),
    dict(abr='WY',name='Wyoming',d='M 652.9,659.4 L 523.9,659.4 L 523.9,539.4 L 652.6,539.4 L 652.9,659.4 Z',cx=580.6,cy=595.5),
]

# Alaska + Hawaii live at projected coords outside the Canada viewBox, so they
# are drawn as fixed insets in the lower-left of the combined "0 0 1608 1180".
US_INSETS = {
    "AK": {"poly": [[40, 1000], [150, 970], [180, 1010], [120, 1060], [180, 1075], [60, 1095], [95, 1050], [45, 1040]], "cx": 110, "cy": 1035},
    "HI": {"poly": [[230, 1095], [250, 1085], [262, 1100], [248, 1112], [270, 1120], [300, 1115], [320, 1135], [300, 1140], [270, 1130], [240, 1122]], "cx": 278, "cy": 1115},
}

US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


# _project_lnglat removed — was dead code; US_STATE_OUTLINES_REAL has pre-projected paths


def build_us_state_paths() -> list[dict]:
    """Return Natural Earth 50m US state SVG paths (pre-projected with EHT formula).
    US_STATE_OUTLINES_REAL has pre-computed d/cx/cy; AK and HI use hardcoded insets."""
    out = [{"abr": s["abr"], "name": s["name"], "d": s["d"],
            "cx": s["cx"], "cy": s["cy"]} for s in US_STATE_OUTLINES_REAL]
    for abr, inset in US_INSETS.items():
        pts = inset["poly"]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
        out.append({"abr": abr, "name": US_STATE_NAMES.get(abr, abr), "d": d,
                    "cx": float(inset["cx"]), "cy": float(inset["cy"])})
    return out


def build_html(jobs: list[dict]) -> str:
    data = {
        "jobs": jobs,
        "center": job_center(jobs),
        "statusColors": STATUS_COLORS,
        "fitColors": FIT_COLORS,
        "axisLabels": AXIS_LABELS,
        "usStatePaths": build_us_state_paths(),
        "today": date.today().isoformat(),
        "coverage": {"sweeps": COV_SWEEPS, "future": COV_FUTURE},
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    html = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job Search Space</title>
  <script src="vendor/three.min.js"></script>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090c12;
      --panel: #111723;
      --panel-2: #151d2a;
      --line: rgba(220, 230, 255, 0.13);
      --text: #eff4ff;
      --muted: #9aa7bd;
      --soft: #c2ccdf;
      --accent: #60a5fa;
      --accent-2: #41d7c8;
      --danger: #f87171;
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { overflow: hidden; }
    button, input { font: inherit; }
    button { color: inherit; }
    .app {
      height: 100vh;
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      grid-template-rows: minmax(0, 100vh);
      background:
        linear-gradient(120deg, rgba(38, 83, 129, 0.12), transparent 28%),
        linear-gradient(180deg, #0b1018, #070a0f 56%, #080b11);
    }
    .sidebar {
      min-height: 0;
      overflow: auto;
      border-right: 1px solid var(--line);
      background: rgba(12, 17, 26, 0.96);
      padding: 14px 12px 16px;
    }
    .brand {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    h1 { margin: 0; font-size: 15px; letter-spacing: 0; }
    .count { color: var(--muted); font-size: 11px; white-space: nowrap; }
    details {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgba(16, 23, 35, 0.74);
      margin-bottom: 9px;
      overflow: hidden;
    }
    /* Nested sub-details inside a parent section */
    .sub-details {
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 6px;
      background: rgba(10,15,25,0.5);
      margin: 4px 0 2px;
      overflow: hidden;
      transition: opacity 0.15s, filter 0.15s;
    }
    .sub-details.labels-off {
      opacity: 0.35;
      filter: grayscale(0.5);
      pointer-events: none;
    }
    .sub-summary {
      cursor: pointer;
      user-select: none;
      list-style: none;
      padding: 6px 10px;
      font-size: 10px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .sub-summary::-webkit-details-marker { display: none; }
    .sub-summary:after { content: "+"; color: #748099; font-size: 12px; }
    .sub-details[open] .sub-summary:after { content: "-"; }
    .sub-section { padding: 0 10px 10px; display: grid; gap: 8px; }
    summary {
      cursor: pointer;
      user-select: none;
      list-style: none;
      padding: 9px 10px;
      font-size: 11px;
      font-weight: 700;
      color: var(--soft);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    summary::-webkit-details-marker { display: none; }
    summary:after { content: "+"; color: #748099; font-size: 13px; }
    details[open] summary:after { content: "-"; }
    .section { padding: 0 10px 11px; display: grid; gap: 9px; }
    .row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .btn {
      border: 1px solid rgba(150, 170, 210, 0.18);
      background: #171f30;
      border-radius: 6px;
      padding: 6px 9px;
      font-size: 12px;
      cursor: pointer;
      min-height: 30px;
    }
    .btn:hover { border-color: rgba(150, 190, 255, 0.38); background: #1d273a; }
    .btn.active { background: #223a60; border-color: rgba(108, 166, 255, 0.68); color: #ddebff; }
    .btn.compact { min-height: 25px; padding: 3px 7px; font-size: 11px; }
    .pill {
      border: 1px solid rgba(150, 170, 210, 0.18);
      border-radius: 999px;
      padding: 5px 8px;
      font-size: 11px;
      cursor: pointer;
      background: rgba(255,255,255,0.04);
      white-space: nowrap;
    }
    .pill.off { opacity: 0.36; filter: grayscale(0.7); }
    .preset-tag {
      display: inline-flex;
      align-items: stretch;
      border: 1px solid rgba(150, 170, 210, 0.18);
      border-radius: 6px;
      overflow: hidden;
      background: #171f30;
    }
    .preset-tag:hover { border-color: rgba(150, 190, 255, 0.38); }
    .preset-load {
      border: 0;
      background: transparent;
      padding: 3px 7px;
      font-size: 11px;
      cursor: pointer;
      color: inherit;
    }
    .preset-del {
      border: 0;
      border-left: 1px solid rgba(150, 170, 210, 0.18);
      background: transparent;
      padding: 3px 7px;
      font-size: 11px;
      cursor: pointer;
      color: var(--danger);
    }
    .preset-del:hover { background: rgba(248, 113, 113, 0.18); }
    .field { display: grid; gap: 5px; }
    .field label { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 11px; }
    .field input[type="range"] { width: 100%; accent-color: #5fa8ff; cursor: pointer; }
    .field input[type="text"] {
      width: 100%;
      border: 1px solid rgba(150, 170, 210, 0.22);
      border-radius: 6px;
      padding: 7px 8px;
      background: #0d1320;
      color: var(--text);
      outline: none;
    }
    .field input[type="text"]:focus { border-color: rgba(96,165,250,0.72); }
    .main {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
    }
    .topbar {
      min-height: 48px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      background: rgba(9, 13, 20, 0.78);
    }
    .title { font-weight: 700; font-size: 14px; }
    .axis-readout { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .workspace {
      min-height: 0;
      min-width: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 260px;
    }
    .scene-wrap {
      position: relative;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      background:
        radial-gradient(circle at 50% 45%, rgba(66, 125, 190, 0.16), transparent 34%),
        linear-gradient(180deg, #0a0f18, #070a0f);
    }
    #scene3d {
      position: absolute;
      inset: 0;
      touch-action: none;
      cursor: grab;
    }
    #scene3d.dragging { cursor: grabbing; }
    .label-layer, .pulse-layer {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }
    .label-layer { z-index: 6; }
    .label-leaders {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 5;
      overflow: visible;
    }
    .job-label {
      position: absolute;
      padding: 2px 5px;
      border-radius: 4px;
      background: rgba(9, 13, 20, 0.78);
      border: 1px solid rgba(255,255,255,0.1);
      color: #dce8ff;
      font-size: 10px;
      white-space: nowrap;
      max-width: 170px;
      overflow: hidden;
      text-overflow: ellipsis;
      opacity: 0;
      transition: opacity 120ms ease;
    }
    .job-label.visible { opacity: 0.92; }
    .axis-label {
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: none;
      white-space: nowrap;
      color: rgba(255,255,255,0.82);
      text-shadow: 0 1px 3px rgba(0,0,0,0.85);
    }
    .axis-label.axis-tick { font-size: 10px; color: rgba(255,255,255,0.7); }
    .axis-label.axis-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #cfe0ff;
    }
    .tooltip {
      position: absolute;
      pointer-events: none;
      min-width: 220px;
      max-width: 310px;
      padding: 9px 10px;
      border: 1px solid rgba(220,230,255,0.16);
      border-radius: var(--radius);
      background: rgba(10, 14, 22, 0.94);
      color: #e7eefc;
      font-size: 12px;
      line-height: 1.45;
      box-shadow: 0 12px 32px rgba(0,0,0,0.36);
      display: none;
      z-index: 7;
    }
    .tooltip strong { display: block; font-size: 13px; margin-bottom: 2px; }
    .map-overlay {
      position: absolute;
      left: 14px;
      bottom: 14px;
      width: min(390px, calc(100% - 28px));
      border: 1px solid rgba(220,230,255,0.16);
      border-radius: var(--radius);
      background: rgba(10, 15, 23, 0.94);
      box-shadow: 0 18px 44px rgba(0,0,0,0.42);
      display: none;
      z-index: 6;
    }
    .map-overlay.open { display: block; }
    .map-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      color: var(--soft);
      font-size: 12px;
      font-weight: 700;
    }
    #location-map { display: block; width: 100%; height: auto; max-height: 360px; }
    .province { fill: #182235; stroke: rgba(230,240,255,0.24); stroke-width: 1; }
    .province-label { fill: #8ea0bd; font-size: 10px; pointer-events: none; }
    .country { fill: #182235; stroke: rgba(230,240,255,0.18); stroke-width: 1; cursor: pointer; transition: fill 120ms ease; }
    .country.ca { fill: #1c2c3f; }
    .country.us { fill: #1a2838; }
    /* No :hover on individual paths — JS adds .country-hover to the whole country group */
    .country.country-hover { fill: #2a3f5c !important; stroke: rgba(120,180,255,0.7); stroke-width: 1.5; }
    .country-label { fill: #cfe0ff; font-size: 30px; font-weight: 700; pointer-events: none; }
    .usstate { fill: #182235; stroke: rgba(230,240,255,0.24); stroke-width: 1; cursor: pointer; transition: fill 120ms ease; }
    .usstate:hover { fill: #28405f; }
    .usstate-label { fill: #8ea0bd; font-size: 11px; font-weight: 600; pointer-events: none; }
    .map-pie-sw {
      border: 1px solid rgba(150,170,210,0.22);
      background: rgba(15,22,36,0.7);
      border-radius: 5px;
      padding: 3px 7px;
      font-size: 10px;
      color: var(--muted);
      cursor: pointer;
      white-space: nowrap;
    }
    .map-pie-sw.active { background: #223a60; border-color: rgba(108,166,255,0.68); color: #ddebff; }
    .map-pie-sw:hover { border-color: rgba(150,190,255,0.38); }
    .map-back {
      border: 1px solid rgba(150, 170, 210, 0.28);
      background: #1d273a;
      border-radius: 6px;
      padding: 3px 9px;
      font-size: 11px;
      cursor: pointer;
      color: var(--soft);
      display: none;
    }
    .map-back.show { display: inline-block; }
    .map-back:hover { border-color: rgba(150, 190, 255, 0.5); }
    .map-hover-label {
      position: absolute;
      pointer-events: auto;
      padding: 7px 9px;
      border-radius: 6px;
      background: rgba(10, 14, 22, 0.96);
      border: 1px solid rgba(96,165,250,0.5);
      color: #e7eefc;
      font-size: 12px;
      white-space: nowrap;
      box-shadow: 0 8px 22px rgba(0,0,0,0.4);
      display: none;
      align-items: center;
      gap: 10px;
      z-index: 8;
    }
    .map-hover-label.show { display: flex; }
    .map-hover-pie { flex: 0 0 auto; line-height: 0; }
    .map-hover-text { display: flex; flex-direction: column; gap: 3px; }
    .map-hover-name { font-weight: 700; font-size: 12px; }
    .map-hover-count { color: var(--muted); font-size: 11px; }
    .map-hover-legend { display: flex; flex-direction: column; gap: 2px; margin-top: 5px; min-width: 0; }
    .legend-item { display: flex; align-items: center; gap: 5px; font-size: 10px; color: var(--soft); white-space: nowrap; }
    .legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .legend-label { color: var(--muted); }
    .pie-axis-row { display: flex; gap: 3px; margin-top: 2px; }
    .pie-axis-btn {
      border: 1px solid rgba(150, 170, 210, 0.28);
      background: #171f30;
      border-radius: 4px;
      padding: 1px 7px;
      font-size: 10px;
      font-weight: 700;
      cursor: pointer;
      color: var(--soft);
    }
    .pie-axis-btn.active { background: #223a60; border-color: rgba(108, 166, 255, 0.7); color: #ddebff; }
    .map-sel {
      border: 1px solid rgba(150, 170, 210, 0.28);
      background: #1d273a;
      border-radius: 6px;
      padding: 3px 8px;
      font-size: 11px;
      cursor: pointer;
      color: var(--soft);
      display: none;
    }
    .map-sel.show { display: inline-block; }
    .map-sel:hover { border-color: rgba(150, 190, 255, 0.5); }
    .map-dot { cursor: pointer; stroke: rgba(5,8,12,0.82); stroke-width: 1.5; transition: r 140ms ease, opacity 140ms ease; }
    .map-dot.dim { opacity: 0.18; }
    .map-dot.hot { r: 7; stroke: white; stroke-width: 2.2; }
    .side-panel {
      min-width: 0;
      min-height: 0;
      border-left: 1px solid var(--line);
      background: rgba(12, 17, 26, 0.86);
      display: flex;
      flex-direction: column;
    }
    /* Collapsible panel wrappers (side panel + timeline) */
    .panel-wrap {
      border: 0;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      margin: 0;
      flex-shrink: 0;
    }
    .panel-wrap > summary { padding: 8px 12px; }
    .panel-wrap.fill[open] {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }
    .panel-wrap.fill[open] > .role-list { flex: 1; min-height: 0; }
    .timeline > details { border: 0; background: transparent; margin: 0; }
    .timeline > details > summary { padding: 2px 0 5px; }
    .timeline-body { display: grid; gap: 5px; }
    .detail {
      padding: 13px 13px 11px;
      border-bottom: 1px solid var(--line);
      min-height: 174px;
    }
    .detail h2 { margin: 0 0 3px; font-size: 16px; line-height: 1.2; }
    .detail .org { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 9px; }
    .chip { border: 1px solid var(--line); border-radius: 5px; padding: 4px 6px; color: var(--soft); font-size: 11px; background: rgba(255,255,255,0.04); }
    .note { color: #c5cfdf; font-size: 12px; line-height: 1.48; }
    .role-list {
      overflow: auto;
      padding: 8px;
      display: grid;
      align-content: start;
      gap: 5px;
    }
    .role-row {
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 8px;
      cursor: pointer;
      background: rgba(255,255,255,0.025);
      display: grid;
      gap: 3px;
    }
    .role-row:hover, .role-row.hot {
      border-color: rgba(118, 181, 255, 0.54);
      background: rgba(74, 130, 200, 0.16);
    }
    .role-row.selected {
      border-color: rgba(65, 215, 200, 0.74);
      background: rgba(65, 215, 200, 0.13);
    }
    .role-line { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; }
    .role-line span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .role-meta { color: var(--muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .timeline {
      border-top: 1px solid var(--line);
      background: rgba(9, 13, 20, 0.88);
      padding: 8px 14px 10px;
      display: grid;
      gap: 5px;
    }
    .timeline-row { display: grid; grid-template-columns: 74px minmax(0, 1fr) 74px auto auto; align-items: center; gap: 9px; }
    .timeline-row span { color: var(--muted); font-size: 11px; }
    .range-wrap { position: relative; height: 24px; display: flex; align-items: center; }
    .range-track, .range-fill { position: absolute; left: 0; right: 0; height: 4px; border-radius: 3px; pointer-events: none; }
    .range-track { background: rgba(255,255,255,0.10); }
    .range-fill { background: linear-gradient(90deg, #558ee8, #39c6bd); }
    .range-wrap input[type="range"] { position: absolute; width: 100%; margin: 0; appearance: none; background: transparent; pointer-events: none; }
    .range-wrap input[type="range"]::-webkit-slider-thumb { appearance: none; pointer-events: auto; cursor: pointer; width: 14px; height: 14px; border-radius: 50%; background: #e6f0ff; border: 3px solid #4285d8; }
    .range-wrap input[type="range"]::-moz-range-thumb { pointer-events: auto; cursor: pointer; width: 14px; height: 14px; border-radius: 50%; background: #e6f0ff; border: 3px solid #4285d8; }
    .today { color: var(--accent-2); }
    .tl-ticks { position: relative; height: 17px; margin: 0 2px; }
    .tl-ticks .tm {
      position: absolute;
      transform: translateX(-50%);
      font-size: 10px;
      color: #7da0e0;
      white-space: nowrap;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .tl-ticks .tm .tmk { width: 1px; height: 5px; background: rgba(120,160,220,0.45); margin-bottom: 1px; }
    .tl-ticks .tm.today { color: var(--accent-2); }
    .tl-ticks .tm.today .tmk { background: rgba(65,215,200,0.7); }
    /* Per-entity strip above the range */
    .tl-entities { position: relative; height: 40px; margin: 0 2px; overflow: hidden; }
    .tl-ent { position: absolute; bottom: 0; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center; pointer-events: none; }
    .tl-ent .lb { font-size: 9px; line-height: 1; color: #cbb7ec; white-space: nowrap; margin-bottom: 2px; letter-spacing: .1px; }
    .tl-ent .tk { width: 1.5px; background: #8a78c8; border-radius: 1px; }
    .tl-ent .dot { width: 4px; height: 4px; border-radius: 50%; background: #b98cff; margin-top: 1px; }
    .tl-controls { display: flex; align-items: center; gap: 7px; padding: 4px 2px 0; flex-wrap: wrap; }
    .tl-ctl-lbl { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .tl-ctl-val { font-size: 10px; color: var(--soft); min-width: 26px; }
    .tl-controls input[type=range] { width: 116px; accent-color: #8b6fe0; }
    .tl-ticks { overflow: hidden; }
    .tl-ent .lb { max-width: 128px; overflow: hidden; text-overflow: ellipsis; }
    .tm.mstart { color: #9fbef0; font-weight: 600; }
    #tl-overview { position: relative; height: 12px; margin: 0 2px 3px; opacity: 0; transition: opacity .45s ease; pointer-events: none; }
    #tl-overview .ovtrack { position: absolute; left: 7px; right: 7px; top: 5px; height: 2px; background: rgba(150,170,220,0.25); border-radius: 1px; }
    #tl-ov-box { position: absolute; top: 1px; height: 10px; border: 1.5px solid #ff5a6a; border-radius: 3px; background: rgba(255,90,106,0.14); box-shadow: 0 0 7px rgba(255,90,106,0.55); }
    .tl-preset { padding: 3px 7px !important; }
    .tl-preset.active { background: #4a3c7e; border-color: #8b6fe0; color: #efeaff; }
    .sum-tog { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; color: var(--muted); font-weight: 400; margin-left: 6px; }
    .sum-tog input { accent-color: #8b6fe0; margin: 0; }
    @media (max-width: 720px) {
      body { overflow: auto; }
      .app { height: auto; min-height: 100vh; grid-template-columns: 1fr; grid-template-rows: minmax(500px, 70vh) auto; }
      .sidebar { max-height: none; border-right: 0; border-top: 1px solid var(--line); }
      .workspace { grid-template-columns: 1fr; grid-template-rows: minmax(460px, 1fr) 360px; }
      .side-panel { border-left: 0; border-top: 1px solid var(--line); }
    }
  </style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <h1>Job Search Space</h1>
      <span class="count" id="job-count">0 roles</span>
    </div>

    <details>
      <summary>Colour</summary>
      <div class="section">
        <div class="row" data-group="color">
          <button class="btn active" data-action="color" data-mode="fit">Fit</button>
          <button class="btn" data-action="color" data-mode="probability">P(int)</button>
          <button class="btn" data-action="color" data-mode="salary">Salary</button>
          <button class="btn" data-action="color" data-mode="status">Status</button>
          <button class="btn" data-action="color" data-mode="location">Location</button>
        </div>
      </div>
    </details>

    <details open>
      <summary>Filter</summary>
      <div class="section">
        <div class="field">
          <label for="filter-text"><span>Search text</span><span id="visible-count">0 visible</span></label>
          <input id="filter-text" type="text" placeholder="director, partnerships, remote">
        </div>
        <div class="field">
          <label for="fit-floor"><span>Fit floor</span><span id="fit-floor-value">1/5</span></label>
          <input id="fit-floor" type="range" min="1" max="5" step="1" value="1">
        </div>
        <div class="field">
          <label><span>Salary</span><span id="salary-range-value">$55K – $220K</span></label>
          <div class="range-wrap">
            <div class="range-track"></div>
            <div class="range-fill" id="salary-fill"></div>
            <input id="salary-min" type="range" min="55" max="220" step="5" value="55">
            <input id="salary-max" type="range" min="55" max="220" step="5" value="220">
          </div>
        </div>
        <div class="row" id="status-pills"></div>
        <div class="row">
          <button class="btn compact" data-action="clear-status">Clear status</button>
          <button class="btn compact" data-action="reset-filters">Reset filters</button>
        </div>
      </div>
    </details>

    <details>
      <summary>Focus <span class="sum-tog"><input type="checkbox" id="focus-vis"><span>cloud on</span></span></summary>
      <div class="section">
        <div class="field">
          <label for="sx"><span>X sector</span><span id="sx-value"></span></label>
          <input id="sx" data-focus="sx" type="range" min="1" max="5" step="0.1">
        </div>
        <div class="field">
          <label for="sy"><span>Y innovation</span><span id="sy-value"></span></label>
          <input id="sy" data-focus="sy" type="range" min="1" max="5" step="0.1">
        </div>
        <div class="field">
          <label for="sz"><span>Z seniority</span><span id="sz-value"></span></label>
          <input id="sz" data-focus="sz" type="range" min="1" max="5" step="0.1">
        </div>
        <div class="field">
          <label for="radius"><span>Radius</span><span id="radius-value"></span></label>
          <input id="radius" data-focus="radius" type="range" min="0.3" max="2.0" step="0.1" value="1">
        </div>
        <div class="field">
          <label for="boundary"><span>Boundary cloud</span><span id="boundary-value"></span></label>
          <input id="boundary" data-focus="boundary" type="range" min="1" max="10" step="1" value="5">
        </div>
        <div class="row">
          <button class="btn compact" data-action="copy-focus">Copy focus</button>
          <button class="btn compact" data-action="save-preset">Save preset</button>
        </div>
        <div class="field">
          <input id="preset-name" type="text" placeholder="Preset name">
        </div>
        <div class="row" id="preset-list"></div>
      </div>
    </details>

    <details open>
      <summary>View</summary>
      <div class="section">
        <div class="row" style="align-items:flex-start;flex-wrap:wrap">
          <div style="display:flex;flex-direction:column;gap:3px">
            <button class="btn active" data-action="toggle-labels">Labels</button>
            <details id="label-fade-details" class="sub-details" style="margin:0;min-width:138px">
              <summary class="sub-summary">Label fade curve</summary>
              <div class="sub-section">
                <div class="field">
                  <label><span>Visible up to</span><span id="label-zoom-value">12</span></label>
                  <input id="label-zoom" type="range" min="6" max="24" step="1" value="12">
                </div>
                <div class="field">
                  <label><span>Fade width</span><span id="label-fade-value">7</span></label>
                  <input id="label-fade" type="range" min="2" max="14" step="1" value="7">
                </div>
              </div>
            </details>
          </div>
          <button class="btn" data-action="toggle-connections">Connections</button>
          <button class="btn" data-action="toggle-salary-rings">Salary rings</button>
          <button class="btn" data-action="toggle-map">Map</button>
        </div>
        <div class="row">
          <button class="btn compact" data-action="reset-camera">Reset camera</button>
          <button class="btn compact" data-action="screenshot">Screenshot</button>
        </div>
      </div>
    </details>

    <details open>
      <summary>Sweeps</summary>
      <div class="section">
        <div class="row" style="flex-wrap:wrap;gap:6px">
          <button class="btn" data-action="toggle-coverage">Show sweeps</button>
          <button class="btn active" data-action="toggle-cov-past">Explored</button>
          <button class="btn active" data-action="toggle-cov-future">Future</button>
        </div>
        <div class="row" style="flex-direction:column;gap:4px;align-items:stretch">
          <div style="display:flex;align-items:center;gap:6px;font-size:10px;color:var(--muted);flex-wrap:wrap">
            <span style="width:11px;height:11px;border-radius:50%;background:linear-gradient(90deg,#3a2a63,#c9a3ff);flex:none"></span>explored (by recency)
            <span style="width:11px;height:11px;border-radius:50%;background:#3fca7d;flex:none;margin-left:6px"></span>future / gap
          </div>
          <div style="font-size:10px;color:var(--muted)">Scrub the <b>Timeline</b> below (or press ▶&nbsp;Play) to sweep the active window across the orbs.</div>
        </div>
      </div>
    </details>
  </aside>

  <main class="main">
    <header class="topbar">
      <div>
        <div class="title">Sector x Innovation x Seniority</div>
        <div class="axis-readout" id="axis-readout"></div>
      </div>
      <div class="axis-readout" id="health-readout">Three.js renderer ready</div>
    </header>

    <section class="workspace">
      <div class="scene-wrap" id="scene-wrap">
        <div id="scene3d" aria-label="3D job search cloud"></div>
        <svg class="label-leaders" id="label-leaders" aria-hidden="true"></svg>
        <div class="label-layer" id="label-layer"></div>
        <div class="tooltip" id="tooltip"></div>
        <div class="map-overlay" id="map-overlay">
          <div class="map-head">
            <span style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
              <button class="map-back" id="map-back" data-action="map-back">&larr; Back</button>
              <span id="map-title">Location map</span>
              <button class="map-sel" id="map-select-all" data-action="map-select-all">Select all</button>
              <button class="map-sel" id="map-deselect-all" data-action="map-deselect-all">Deselect all</button>
            </span>
            <span style="display:flex;align-items:center;gap:5px">
              <span style="font-size:10px;color:#9aa7bd;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap">Pie axis</span>
              <button class="map-pie-sw active" data-pie-axis="x">Sector</button>
              <button class="map-pie-sw" data-pie-axis="y">Innovation</button>
              <button class="map-pie-sw" data-pie-axis="z">Seniority</button>
              <button class="btn compact" data-action="toggle-map" style="margin-left:4px">Close</button>
            </span>
          </div>
          <svg id="location-map" viewBox="0 0 1608 1180" role="img" aria-label="Location map"></svg>
          <div class="map-hover-label" id="map-hover-label"></div>
        </div>
      </div>

      <aside class="side-panel">
        <details class="panel-wrap" open>
          <summary>Role detail</summary>
          <div class="detail" id="detail"></div>
        </details>
        <details class="panel-wrap fill" open>
          <summary>Roles</summary>
          <div class="role-list" id="role-list"></div>
        </details>
      </aside>
    </section>

    <footer class="timeline">
      <details open>
        <summary>Timeline</summary>
        <div class="timeline-body">
          <div id="tl-overview"><div class="ovtrack"></div><div id="tl-ov-box"></div></div>
          <div class="timeline-row">
            <span></span>
            <div class="tl-entities" id="tl-entities"></div>
            <span></span><span></span><span></span>
          </div>
          <div class="timeline-row">
            <span id="tl-start-label"></span>
            <div class="range-wrap">
              <div class="range-track"></div>
              <div class="range-fill" id="timeline-fill"></div>
              <input id="tl-start" type="range" min="0" max="100" value="0">
              <input id="tl-end" type="range" min="0" max="100" value="100">
            </div>
            <span id="tl-end-label"></span>
            <button class="btn compact" id="tl-play">&#9654; Play</button>
            <button class="btn compact" data-action="reset-timeline">Reset</button>
          </div>
          <div class="timeline-row">
            <span></span>
            <div class="tl-ticks" id="tl-ticks"></div>
            <span></span>
            <span></span>
          </div>
          <div class="tl-controls">
            <span class="tl-ctl-lbl">Speed</span>
            <input id="tl-speed" type="range" min="0.25" max="4" step="0.25" value="1">
            <span id="tl-speed-val" class="tl-ctl-val">1&times;</span>
            <span class="tl-ctl-lbl" style="margin-left:8px">Zoom</span>
            <input id="tl-zoom" type="range" min="1" max="8" step="0.5" value="1">
            <span id="tl-zoom-val" class="tl-ctl-val">1&times;</span>
            <span class="tl-ctl-lbl" style="margin-left:10px">View</span>
            <button class="btn compact tl-preset" data-days="all">All</button>
            <button class="btn compact tl-preset" data-days="90">3&#8202;mo</button>
            <button class="btn compact tl-preset active" data-days="30">Month</button>
            <button class="btn compact tl-preset" data-days="7">Week</button>
            <button class="btn compact tl-preset" data-days="fit">Fit</button>
          </div>
        </div>
      </details>
    </footer>
  </main>
</div>

<script id="job-data" type="application/json">__PAYLOAD__</script>
<script>
(function () {
  "use strict";

  const DATA = JSON.parse(document.getElementById("job-data").textContent);
  const JOBS = DATA.jobs;
  const STATUS_COLORS = DATA.statusColors;
  const FIT_COLORS = DATA.fitColors;
  const AXIS_LABELS = DATA.axisLabels;
  const US_STATE_PATHS = DATA.usStatePaths || [];
  const BOUNDARY_LABELS = ["", "Very strict", "Strict", "Fairly strict", "Moderate", "Medium", "Fairly loose", "Loose", "Very loose", "Very loose", "Fuzzy"];
  const LOCATION_COLORS = { AB: "#44c7e8", BC: "#7dd3a8", SK: "#e7c85d", MB: "#f59e0b", ON: "#a887ff", QC: "#f472b6", Remote: "#d1d5db" };
  const OUTCOMES = ["pending", "offer", "no-offer", "waitlisted"];
  const OUTCOME_COLORS = { pending: "#e0b15b", offer: "#46c08a", "no-offer": "#d73027", waitlisted: "#a78bfa" };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const lerp = (a, b, t) => a + (b - a) * t;
  const dateMs = (iso) => new Date(iso + "T00:00:00").getTime();
  const fmtDate = (iso) => iso ? iso.slice(2) : "-";

  const state = window._vizState = {  // expose for devtools / test harness
    colorMode: "fit",
    filters: { text: "", fitFloor: 1, salaryMin: 55, salaryMax: 220, statuses: new Set(Object.keys(STATUS_COLORS)), province: new Set(), country: null },
    mapTier: "countries",   // "countries" | "CA" | "US"
    mapPieAxis: "x",        // hover-pie axis: "x" sector | "y" innovation | "z" seniority
    focus: { sx: DATA.center.x, sy: DATA.center.y, sz: DATA.center.z, radius: 1, boundary: 5 },
    timeline: { startPct: 0, endPct: 100, startDate: null, endDate: null },
    showLabels: true,
    labelZoom: 12,   // radius at which labels are fully gone (fully visible below zoom-fade)
    labelFade: 7,    // width of the fade zone
    showConnections: false,
    showCoverage: false,
    covPast: true,
    covFuture: true,
    showFocus: false,
    showSalaryRings: false,
    showMap: false,
    hoveredId: null,
    selectedId: JOBS[0] ? JOBS[0].id : null,
  };

  let renderer, scene, camera;
  let jobGroup, ringGroup, lineGroup, focusPoints, focusOutline;
  let coverageGroup;
  let raycaster, pointer, sceneWrap, sceneEl, labelLayer, leaderSvg, tooltip;
  const SVG_NS = "http://www.w3.org/2000/svg";
  let width = 1, height = 1;
  let dirtyScene = true;
  let dirtyFilter = true;
  let dirtyFocus = true;
  let dirtyMap = true;
  let dirtyList = true;
  let dragging = false;
  let dragStart = { x: 0, y: 0, theta: 0, phi: 0 };
  let orbit = { theta: Math.PI * 0.25, phi: Math.PI * 0.34, radius: 9.2 };
  const jobObjects = new Map();
  const labelEls = new Map();
  const axisLabels = [];
  const jobById = new Map(JOBS.map((j) => [j.id, j]));
  const visibleIds = new Set();
  // Interview outcomes — seeded from data, mutable during session (not persisted).
  const jobOutcomes = new Map();
  JOBS.forEach((j) => { if (j.outcome !== null && j.outcome !== undefined) jobOutcomes.set(j.id, j.outcome || "pending"); });

  function cycleOutcome(id) {
    const cur = jobOutcomes.get(id) || "pending";
    const next = OUTCOMES[(OUTCOMES.indexOf(cur) + 1) % OUTCOMES.length];
    jobOutcomes.set(id, next);
    renderDetail();
  }

  const allDates = [...new Set(JOBS.map((j) => j.date).filter(Boolean))].sort();
  const minDate = allDates[0] || "2026-01-01";
  const maxDate = allDates[allDates.length - 1] || minDate;

  function worldFromJob(job) {
    return new THREE.Vector3((job.x - 3) * -1.82, (job.z - 3) * 1.58, (job.y - 3) * -1.82);
  }

  // ---- Sweep-coverage layer: purple = explored (by recency), green = future ----
  const covMeshes = [];
  const covLabels = [];
  const entityEls = [];
  let covDays = 30, covPlaying = false, covTmin = 0, covTmax = 1, covUIInit = false;
  const covRay = new THREE.Raycaster();
  let covTip = null;
  function covRecencyColor(t) {
    const f = covTmax > covTmin ? (t - covTmin) / (covTmax - covTmin) : 1;
    const c1 = [0x3a, 0x2a, 0x63], c2 = [0xc9, 0xa3, 0xff];
    return new THREE.Color((c1[0]+(c2[0]-c1[0])*f)/255, (c1[1]+(c2[1]-c1[1])*f)/255, (c1[2]+(c2[2]-c1[2])*f)/255);
  }
  function buildCoverage() {
    const cov = DATA.coverage || { sweeps: [], future: [] };
    const done = (cov.sweeps || []).map(s => Object.assign({}, s, { t: Date.parse(s.date) }));
    if (done.length) { covTmin = Math.min.apply(null, done.map(s=>s.t)); covTmax = Math.max.apply(null, done.map(s=>s.t)); }
    // de-stack: fan out spheres sharing a grid cell so they don't pile up
    const cellKey = s => Math.round(s.x*2)+","+Math.round(s.y*2)+","+Math.round(s.z*2);
    const cellTotal = {}, cellIdx = {};
    done.concat(cov.future || []).forEach(s => { const k = cellKey(s); cellTotal[k] = (cellTotal[k]||0)+1; });
    function mk(s, isFuture) {
      const rad = 0.22 + (s.r || 0.7) * 0.24;
      const col = isFuture ? new THREE.Color(0x3fca7d) : covRecencyColor(s.t);
      const mat = new THREE.MeshStandardMaterial({ color: col, transparent: true,
        opacity: isFuture ? 0.26 : 0.8, emissive: col, emissiveIntensity: isFuture ? 0.45 : 0.25,
        roughness: 0.4, metalness: 0.08 });
      const m = new THREE.Mesh(new THREE.SphereGeometry(rad, 30, 22), mat);
      let cpos = worldFromJob(s);
      const _k = cellKey(s), _n = cellTotal[_k];
      if (_n > 1) { const _i = (cellIdx[_k] = (cellIdx[_k]||0)); cellIdx[_k]++;
        const _a = (_i / _n) * Math.PI * 2, _rr = 0.85 + _n*0.12;
        const _vy = (_i - (_n-1)/2) * 0.55;   // stagger vertically so labels don't overlap
        cpos = cpos.clone().add(new THREE.Vector3(Math.cos(_a)*_rr, _vy, Math.sin(_a)*_rr)); }
      m.position.copy(cpos);
      m.userData.cov = Object.assign({}, s, { isFuture: isFuture });
      coverageGroup.add(m); covMeshes.push(m);
      const lab = document.createElement("div");
      lab.textContent = shortCov(s.label);
      lab.style.cssText = "position:absolute;pointer-events:none;font:600 10px/1.2 Inter,system-ui,sans-serif;white-space:nowrap;padding:1px 5px;border-radius:5px;transform:translate(-50%,-150%);background:rgba(13,11,20,.72);opacity:0;transition:opacity .12s;color:" + (isFuture ? "#8ff0bd" : "#e0c9ff") + ";border:1px solid " + (isFuture ? "#2f7d55" : "#4a3c7e");
      labelLayer.appendChild(lab);
      covLabels.push({ el: lab, mesh: m });
      if (isFuture) {
        const halo = new THREE.Mesh(new THREE.SphereGeometry(rad*1.03, 18, 12),
          new THREE.MeshBasicMaterial({ color: 0x6ff0aa, wireframe: true, transparent: true, opacity: 0.32 }));
        m.add(halo);
      }
    }
    done.forEach(s => mk(s, false));
    (cov.future || []).forEach(s => mk(s, true));
    initCoverageUI();
    refreshCoverage();
  }
  // Orbs are driven by the MAIN timeline (state.timeline.startDate/endDate).
  function refreshCoverage() {
    const sd = state.timeline.startDate, ed = state.timeline.endDate;   // ISO strings or null
    const hiMs = ed ? dateMs(ed) : covTmax, loMs = sd ? dateMs(sd) : covTmin;
    const span = Math.max(1, hiMs - loMs);
    covMeshes.forEach(m => {
      const d = m.userData.cov;
      if (d.isFuture) { m.visible = state.covFuture; return; }
      const inWin = (!sd || d.date >= sd) && (!ed || d.date <= ed);
      m.visible = state.covPast && inWin;
      if (inWin) {
        const edge = Math.max(0, 1 - (hiMs - d.t) / span);  // brightest at the window's recent (leading) edge
        m.material.opacity = 0.34 + 0.5 * edge;
        m.material.emissiveIntensity = 0.2 + 0.5 * edge;
        m.scale.setScalar(0.92 + 0.24 * edge);
      }
    });
  }
  function shortCov(t) {
    let s = String(t).split(" (")[0].split(" — ")[0].split(" / ")[0].split(":")[0];
    return s.length > 30 ? s.slice(0, 29) + "…" : s;
  }
  function updateCoverageLabels() {
    if (!covLabels.length) return;
    const on = state.showCoverage;
    for (const c of covLabels) {
      if (!on || !c.mesh.visible) { c.el.style.opacity = 0; continue; }
      const p = c.mesh.position.clone().project(camera);
      if (p.z > 1) { c.el.style.opacity = 0; continue; }
      c.el.style.left = ((p.x * 0.5 + 0.5) * width).toFixed(1) + "px";
      c.el.style.top = ((-p.y * 0.5 + 0.5) * height).toFixed(1) + "px";
      c.el.style.opacity = 1;
    }
  }
  function initCoverageUI() {
    if (covUIInit) return; covUIInit = true;
    covTip = document.createElement("div");
    covTip.style.cssText = "position:fixed;pointer-events:none;z-index:60;background:rgba(10,8,18,.96);border:1px solid #2a2438;border-radius:8px;padding:8px 10px;max-width:260px;font-size:11.5px;line-height:1.4;color:#e9e6f5;opacity:0;transition:opacity .1s";
    document.body.appendChild(covTip);
    if (renderer && renderer.domElement) renderer.domElement.addEventListener("pointermove", covOnMove);
  }
  function covOnMove(ev) {
    if (!state.showCoverage || !covTip) { if (covTip) covTip.style.opacity = 0; return; }
    const r = renderer.domElement.getBoundingClientRect();
    const mx = ((ev.clientX - r.left) / r.width) * 2 - 1, my = -((ev.clientY - r.top) / r.height) * 2 + 1;
    covRay.setFromCamera({ x: mx, y: my }, camera);
    const hit = covRay.intersectObjects(covMeshes.filter(m => m.visible), false)[0];
    if (hit) {
      const d = hit.object.userData.cov;
      const when = d.isFuture ? "planned" : new Date(d.t).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
      covTip.innerHTML = "<b style='color:#e9c9ff'>" + d.label + "</b><br><span style='color:#9a93b5'>" + d.prong + " · " + when + (d.count ? (" · " + d.count + " roles") : "") + "</span>" + (d.notes ? ("<br><span style='color:#9a93b5'>" + d.notes + "</span>") : "");
      covTip.style.left = (ev.clientX + 14) + "px"; covTip.style.top = (ev.clientY + 14) + "px"; covTip.style.opacity = 1;
    } else covTip.style.opacity = 0;
  }

  function colorFor(job) {
    if (state.colorMode === "fit") return FIT_COLORS[clamp(job.fit, 1, 5) - 1];
    if (state.colorMode === "probability") {
      const t = clamp(job.p / 35, 0, 1);
      return rgbToHex(lerp(190, 70, t), lerp(84, 204, t), lerp(84, 128, t));
    }
    if (state.colorMode === "salary") {
      const t = clamp((job.sal - 55) / 165, 0, 1);
      return rgbToHex(lerp(92, 250, t), lerp(170, 204, t), lerp(255, 90, t));
    }
    if (state.colorMode === "location") return LOCATION_COLORS[job.province] || "#d1d5db";
    return STATUS_COLORS[job.status] || "#9aa7bd";
  }

  function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map((v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0")).join("");
  }

  function baseScale(job) {
    if (job.status === "Interview") return 0.18;
    if (job.status === "Target") return 0.12;
    return 0.135;
  }

  const CA_PROVINCES = new Set(["AB","BC","SK","MB","ON","QC","NB","NS","PE","NL","YT","NT","NU"]);
  const US_STATES_SET = new Set(["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]);

  // Map a job's province/state abbreviation to a country code ("CA" | "US" | null for Remote).
  function jobCountry(job) {
    const p = job.province;
    if (CA_PROVINCES.has(p)) return "CA";
    if (US_STATES_SET.has(p)) return "US";
    return null;
  }

  function jobVisible(job) {
    const f = state.filters;
    if (!f.statuses.has(job.status)) return false;
    if (job.fit < f.fitFloor) return false;
    if (job.sal < f.salaryMin || job.sal > f.salaryMax) return false;
    if (state.timeline.startDate && job.date < state.timeline.startDate) return false;
    if (state.timeline.endDate && job.date > state.timeline.endDate) return false;
    if (f.country === "__none__") return false;
    if (f.country && f.country !== "__none__" && jobCountry(job) !== f.country) return false;
    if (f.province === "__none__") return false;  // deselect-all sentinel
    if (f.province instanceof Set && f.province.size > 0 && !f.province.has(job.province)) return false;
    if (f.text) {
      const hay = (job.label + " " + job.org + " " + job.status + " " + job.place + " " + (job.note || "")).toLowerCase();
      if (!hay.includes(f.text)) return false;
    }
    return true;
  }

  function initThree() {
    if (!window.THREE) {
      $("#health-readout").textContent = "Three.js failed to load";
      return;
    }
    sceneWrap = $("#scene-wrap");
    sceneEl = $("#scene3d");
    labelLayer = $("#label-layer");
    leaderSvg = $("#label-leaders");
    tooltip = $("#tooltip");
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080c12);

    camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    sceneEl.appendChild(renderer.domElement);

    raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 0.08;
    pointer = new THREE.Vector2();

    const amb = new THREE.AmbientLight(0xffffff, 0.68);
    scene.add(amb);
    const key = new THREE.DirectionalLight(0xdcebff, 1.1);
    key.position.set(3, 6, 5);
    scene.add(key);

    jobGroup = new THREE.Group();
    ringGroup = new THREE.Group();
    lineGroup = new THREE.Group();
    coverageGroup = new THREE.Group();
    coverageGroup.visible = false;
    scene.add(jobGroup, ringGroup, lineGroup, coverageGroup);

    buildGrid();
    buildJobs();
    buildCoverage();
    rebuildFocusCloud();
    resizeScene();
    resetCamera();

    const ro = new ResizeObserver(resizeScene);
    ro.observe(sceneWrap);
    window.addEventListener("resize", resizeScene);
    sceneEl.addEventListener("pointerdown", onPointerDown);
    sceneEl.addEventListener("pointermove", onPointerMove);
    sceneEl.addEventListener("pointerup", onPointerUp);
    sceneEl.addEventListener("pointercancel", onPointerUp);
    sceneEl.addEventListener("mouseleave", () => { if (!dragging) setHover(null); });
    sceneEl.addEventListener("wheel", onWheel, { passive: false });
    sceneEl.addEventListener("click", onSceneClick);

    requestAnimationFrame(animate);
  }

  function buildGrid() {
    const matGrid = new THREE.LineBasicMaterial({ color: 0x334057, transparent: true, opacity: 0.55 });
    const matAxis = new THREE.LineBasicMaterial({ color: 0x7898c8, transparent: true, opacity: 0.9 });
    const lines = [];
    for (let i = 1; i <= 5; i++) {
      const a = worldFromJob({ x: i, y: 1, z: 1 });
      const b = worldFromJob({ x: i, y: 5, z: 1 });
      const c = worldFromJob({ x: 1, y: i, z: 1 });
      const d = worldFromJob({ x: 5, y: i, z: 1 });
      lines.push(a, b, c, d);
    }
    const geo = new THREE.BufferGeometry().setFromPoints(lines);
    scene.add(new THREE.LineSegments(geo, matGrid));

    const axisPts = [
      worldFromJob({ x: 1, y: 1, z: 1 }), worldFromJob({ x: 5.35, y: 1, z: 1 }),
      worldFromJob({ x: 1, y: 1, z: 1 }), worldFromJob({ x: 1, y: 5.35, z: 1 }),
      worldFromJob({ x: 1, y: 1, z: 1 }), worldFromJob({ x: 1, y: 1, z: 5.35 }),
    ];
    scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(axisPts), matAxis));

    buildAxisDecor();
  }

  // Axis tick marks (3D line segments) + HTML tick/title labels projected each frame.
  function buildAxisDecor() {
    const tickMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 });
    const tickPts = [];
    const tick = 0.16; // tick half-length in scene units

    for (let i = 1; i <= 5; i++) {
      // Store the TICK world position (not an offset) — screen-space offset applied in updateAxisLabels
      let p = worldFromJob({ x: i, y: 1, z: 1 });
      tickPts.push(new THREE.Vector3(p.x, p.y - tick, p.z), new THREE.Vector3(p.x, p.y + tick, p.z));
      addAxisLabel(new THREE.Vector3(p.x, p.y, p.z), AXIS_LABELS.x[i], "axis-tick axis-tick-x");

      p = worldFromJob({ x: 1, y: i, z: 1 });
      tickPts.push(new THREE.Vector3(p.x, p.y, p.z - tick), new THREE.Vector3(p.x, p.y, p.z + tick));
      addAxisLabel(new THREE.Vector3(p.x, p.y, p.z), AXIS_LABELS.y[i], "axis-tick axis-tick-y");

      p = worldFromJob({ x: 1, y: 1, z: i });
      tickPts.push(new THREE.Vector3(p.x - tick, p.y, p.z), new THREE.Vector3(p.x + tick, p.y, p.z));
      addAxisLabel(new THREE.Vector3(p.x, p.y, p.z), AXIS_LABELS.z[i], "axis-tick axis-tick-z");
    }
    scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(tickPts), tickMat));

    // Axis titles — positioned just past the end of each axis line (5.35), not far beyond
    addAxisLabel(worldFromJob({ x: 5.5, y: 1, z: 1 }), "X · Sector", "axis-title");
    addAxisLabel(worldFromJob({ x: 1, y: 5.5, z: 1 }), "Y · Innovation", "axis-title");
    addAxisLabel(worldFromJob({ x: 1, y: 1, z: 5.5 }), "Z · Seniority", "axis-title");
  }

  function addAxisLabel(worldPos, text, cls) {
    const el = document.createElement("div");
    el.className = "axis-label " + cls;
    el.textContent = text;
    labelLayer.appendChild(el);
    axisLabels.push({ el, pos: worldPos });
  }

  function updateAxisLabels() {
    if (!camera || !axisLabels.length) return;
    for (const a of axisLabels) {
      const v = a.pos.clone().project(camera);
      if (v.z > 1) { a.el.style.display = "none"; continue; }
      a.el.style.display = "";
      const sx = (v.x * 0.5 + 0.5) * width;
      const sy = (-v.y * 0.5 + 0.5) * height;
      // Screen-space offset: Y and Z ticks always go LEFT of the projected tick (right-aligned, -16px gap)
      // X ticks hang 10px below (centered). Titles stay centered.
      if (a.el.classList.contains("axis-tick-z") || a.el.classList.contains("axis-tick-y")) {
        a.el.style.left = (sx - 16).toFixed(1) + "px";
        a.el.style.top  = sy.toFixed(1) + "px";
        a.el.style.transform = "translate(-100%, -50%)";
        a.el.style.textAlign = "right";
      } else if (a.el.classList.contains("axis-tick-x")) {
        a.el.style.left = sx.toFixed(1) + "px";
        a.el.style.top  = (sy + 16).toFixed(1) + "px";
        a.el.style.transform = "translate(-50%, 0)";
        a.el.style.textAlign = "center";
      } else {
        a.el.style.left = sx.toFixed(1) + "px";
        a.el.style.top  = sy.toFixed(1) + "px";
        a.el.style.transform = "translate(-50%, -50%)";
        a.el.style.textAlign = "center";
      }
    }
  }

  function buildJobs() {
    const sphere = new THREE.SphereGeometry(1, 24, 18);
    const diamond = new THREE.OctahedronGeometry(1, 0);
    const target = new THREE.TetrahedronGeometry(1, 0);
    JOBS.forEach((job) => {
      const geom = job.status === "Interview" ? diamond : job.status === "Target" ? target : sphere;
      const mat = new THREE.MeshStandardMaterial({
        color: colorFor(job),
        roughness: 0.48,
        metalness: 0.08,
        emissive: 0x000000,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.copy(worldFromJob(job));
      mesh.scale.setScalar(baseScale(job));
      mesh.userData.jobId = job.id;
      jobGroup.add(mesh);
      jobObjects.set(job.id, mesh);

      const label = document.createElement("div");
      label.className = "job-label";
      label.textContent = job.label;
      labelLayer.appendChild(label);
      labelEls.set(job.id, label);
    });
  }

  function spherePointCloud(cx, cy, cz, radius, boundary) {
    const strict = 11 - boundary;
    const n = Math.round(260 + strict * 32);
    const disp = Math.max(0, (10 - strict) / 10 * 1.4); // more scatter at fuzzy end
    const pts = new Float32Array(n * 3);
    const gr = (1 + Math.sqrt(5)) / 2;
    for (let i = 0; i < n; i++) {
      const theta = Math.acos(1 - 2 * (i + 0.5) / n);
      const phi = 2 * Math.PI * i / gr;
      const jitter = 1 + disp * (Math.cos(i * 7.389 + theta) * 0.6 + Math.sin(i * 2.718 + phi) * 0.4);
      const x = cx + radius * jitter * Math.sin(theta) * Math.cos(phi);
      const y = cy + radius * jitter * Math.sin(theta) * Math.sin(phi);
      const z = cz + radius * 0.8 * jitter * Math.cos(theta);
      const v = worldFromJob({ x, y, z });
      pts[i * 3] = v.x;
      pts[i * 3 + 1] = v.y;
      pts[i * 3 + 2] = v.z;
    }
    return pts;
  }

  function rebuildFocusCloud() {
    const f = state.focus;
    const positions = spherePointCloud(f.sx, f.sy, f.sz, f.radius, f.boundary);
    if (focusPoints) scene.remove(focusPoints);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const alpha = 0.32 + f.boundary * 0.028; // brighter dots
    const mat = new THREE.PointsMaterial({
      color: 0x74b8ff,
      size: 0.085, // larger dots — were barely visible at 0.045
      transparent: true,
      opacity: alpha,
      depthWrite: false,
    });
    focusPoints = new THREE.Points(geo, mat);
    focusPoints.visible = state.showFocus;
    scene.add(focusPoints);
    rebuildFocusOutline();
    dirtyFocus = false;
  }

  function rebuildFocusOutline() {
    if (focusOutline) scene.remove(focusOutline);
    const f = state.focus;
    const pts = [];
    const lat = 6, lon = 12;
    for (let a = 1; a < lat; a++) {
      const theta = Math.PI * a / lat;
      for (let b = 0; b < lon; b++) {
        const p1 = sphereSurface(f, theta, 2 * Math.PI * b / lon);
        const p2 = sphereSurface(f, theta, 2 * Math.PI * (b + 1) / lon);
        pts.push(p1, p2);
      }
    }
    for (let b = 0; b < lon; b++) {
      const phi = 2 * Math.PI * b / lon;
      for (let a = 0; a < lat; a++) {
        pts.push(sphereSurface(f, Math.PI * a / lat, phi), sphereSurface(f, Math.PI * (a + 1) / lat, phi));
      }
    }
    const mat = new THREE.LineBasicMaterial({ color: 0x79b8ff, transparent: true, opacity: 0.22 });
    focusOutline = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat);
    focusOutline.visible = state.showFocus;
    scene.add(focusOutline);
  }

  function sphereSurface(f, theta, phi) {
    return worldFromJob({
      x: f.sx + f.radius * Math.sin(theta) * Math.cos(phi),
      y: f.sy + f.radius * Math.sin(theta) * Math.sin(phi),
      z: f.sz + f.radius * 0.8 * Math.cos(theta),
    });
  }

  function updateCamera() {
    const eps = 0.05;
    orbit.phi = clamp(orbit.phi, eps, Math.PI - eps);
    camera.position.set(
      orbit.radius * Math.sin(orbit.phi) * Math.cos(orbit.theta),
      orbit.radius * Math.cos(orbit.phi),
      orbit.radius * Math.sin(orbit.phi) * Math.sin(orbit.theta)
    );
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }

  function resetCamera() {
    orbit = { theta: Math.PI * 0.25, phi: Math.PI * 0.34, radius: 9.2 };
    updateCamera();
  }

  function resizeScene() {
    if (!renderer || !sceneWrap) return;
    const rect = sceneWrap.getBoundingClientRect();
    width = Math.max(1, Math.floor(rect.width));
    height = Math.max(1, Math.floor(rect.height));
    renderer.setSize(width, height, true);  // true = also update canvas CSS style so HiDPI doesn't misalign labels
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderEntityStrip();
  }

  function onPointerDown(ev) {
    if (ev.button !== 0) return;
    dragging = true;
    sceneEl.classList.add("dragging");
    sceneEl.setPointerCapture(ev.pointerId);
    dragStart = { x: ev.clientX, y: ev.clientY, theta: orbit.theta, phi: orbit.phi };
  }

  function onPointerMove(ev) {
    const rect = sceneEl.getBoundingClientRect();
    pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -(((ev.clientY - rect.top) / rect.height) * 2 - 1);

    if (dragging) {
      const dx = ev.clientX - dragStart.x;
      const dy = ev.clientY - dragStart.y;
      orbit.theta = dragStart.theta + dx * 0.008;
      orbit.phi = dragStart.phi - dy * 0.008;
      updateCamera();
      return;
    }
    if (!state.showMap) raycastHover(ev);  // don't ray-cast through open map overlay
  }

  function onPointerUp(ev) {
    dragging = false;
    sceneEl.classList.remove("dragging");
    try { sceneEl.releasePointerCapture(ev.pointerId); } catch (err) {}
  }

  function onWheel(ev) {
    ev.preventDefault();
    orbit.radius = clamp(orbit.radius + ev.deltaY * 0.007, 4.5, 26);
    updateCamera();
  }

  function raycastHover(ev) {
    if (!raycaster || !camera) return;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(Array.from(jobObjects.values()).filter((mesh) => mesh.visible), false);
    const id = hits.length ? hits[0].object.userData.jobId : null;
    // No ev → no tooltip in the 3D scene; the hover label already shows the name
    setHover(id);
  }

  function onSceneClick(ev) {
    if (dragging) return;
    // Click on the 3D scene closes the map overlay
    if (state.showMap) { state.showMap = false; dirtyMap = true; return; }
    if (state.hoveredId) selectJob(state.hoveredId);
  }

  function setHover(id, ev) {
    if (state.hoveredId === id) {
      if (id && ev) moveTooltip(ev);
      return;
    }
    state.hoveredId = id;
    dirtyMap = true;
    dirtyList = true;
    if (id && ev) showTooltip(id, ev);
    else tooltip.style.display = "none";
  }

  function selectJob(id) {
    if (!id) return;
    state.selectedId = id;
    dirtyList = true;
    dirtyMap = true;
    renderDetail();
  }

  function showTooltip(id, ev) {
    const job = jobById.get(id);
    if (!job) return;
    tooltip.innerHTML =
      "<strong>" + escapeHtml(job.label) + "</strong>" +
      escapeHtml(job.org) + "<br>" +
      "Fit " + job.fit + "/5 | P(int) " + job.p + "% | $" + job.sal + "K<br>" +
      escapeHtml(job.status + " | " + job.place);
    tooltip.style.display = "block";
    moveTooltip(ev);
  }

  function moveTooltip(ev) {
    const rect = sceneWrap.getBoundingClientRect();
    const left = clamp(ev.clientX - rect.left + 14, 8, rect.width - 328);
    const top = clamp(ev.clientY - rect.top + 14, 8, rect.height - 132);
    tooltip.style.left = left + "px";
    tooltip.style.top = top + "px";
  }

  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function applyFilters() {
    visibleIds.clear();
    JOBS.forEach((job) => { if (jobVisible(job)) visibleIds.add(job.id); });
    dirtyFilter = false;
    dirtyScene = true;
    dirtyMap = true;
    dirtyList = true;
    $("#visible-count").textContent = visibleIds.size + " visible";
  }

  function syncSceneState(time) {
    if (dirtyFilter) applyFilters();
    if (dirtyFocus) rebuildFocusCloud();
    const rebuildOverlays = dirtyScene;

    JOBS.forEach((job) => {
      const mesh = jobObjects.get(job.id);
      const visible = visibleIds.has(job.id);
      const hot = job.id === state.hoveredId || job.id === state.selectedId;
      const pulse = hot ? 1 + Math.sin(time * 0.006) * 0.08 + 0.18 : 1;
      mesh.visible = visible;
      mesh.material.color.set(colorFor(job));
      mesh.material.emissive.set(hot ? 0x17395f : 0x000000);
      mesh.scale.setScalar(baseScale(job) * pulse);

      const label = labelEls.get(job.id);
      if (label) {
        // When labels are off, only the actively hovered job gets the visible class (not selected)
        label.classList.toggle("visible", visible && (state.showLabels || job.id === state.hoveredId));
      }
    });
    if (rebuildOverlays) {
      renderConnections();
      renderSalaryRings();
      dirtyScene = false;
    }
  }

  function renderConnections() {
    lineGroup.clear();
    if (!state.showConnections) return;
    const interviews = JOBS.filter((j) => j.status === "Interview" && visibleIds.has(j.id));
    const targets = JOBS.filter((j) => j.status !== "Interview" && visibleIds.has(j.id));
    const pts = [];
    interviews.forEach((iv) => {
      let best = null, bestD = Infinity;
      targets.forEach((t) => {
        const d = Math.hypot(iv.x - t.x, iv.y - t.y, iv.z - t.z);
        if (d < bestD) { best = t; bestD = d; }
      });
      if (best) pts.push(worldFromJob(iv), worldFromJob(best));
    });
    if (!pts.length) return;
    const mat = new THREE.LineBasicMaterial({ color: 0xffcf6b, transparent: true, opacity: 0.5 });
    lineGroup.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat));
  }

  function renderSalaryRings() {
    ringGroup.clear();
    if (!state.showSalaryRings) return;
    JOBS.forEach((job) => {
      if (!visibleIds.has(job.id)) return;
      const r = 0.18 + clamp((job.sal - 55) / 170, 0, 1) * 0.26;
      const geom = new THREE.RingGeometry(r, r + 0.018, 36);
      const mat = new THREE.MeshBasicMaterial({ color: colorFor(job), transparent: true, opacity: 0.26, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(geom, mat);
      ring.position.copy(worldFromJob(job));
      ring.userData.billboard = true;
      ringGroup.add(ring);
    });
  }

  function updateLabels() {
    if (!camera) return;
    const zoomOpacity = Math.max(0, Math.min(1, (state.labelZoom - orbit.radius) / Math.max(1, state.labelFade)));

    // When hovering, find the 5 nearest visible jobs in screen space
    const nearbyIds = new Set();
    if (state.hoveredId) {
      const hj = jobById.get(state.hoveredId);
      if (hj) {
        const hv = worldFromJob(hj).clone().project(camera);
        const hsx = (hv.x * 0.5 + 0.5) * width;
        const hsy = (-hv.y * 0.5 + 0.5) * height;
        const dists = [];
        JOBS.forEach((j) => {
          if (j.id === state.hoveredId || !visibleIds.has(j.id)) return;
          const v = worldFromJob(j).clone().project(camera);
          if (v.z > 1) return;
          const sx = (v.x * 0.5 + 0.5) * width;
          const sy = (-v.y * 0.5 + 0.5) * height;
          dists.push({ id: j.id, d: (sx - hsx) ** 2 + (sy - hsy) ** 2 });
        });
        dists.sort((a, b) => a.d - b.d);
        dists.slice(0, 5).forEach((e) => nearbyIds.add(e.id));
      }
    }

    // Collision detection for global (Labels-toggle) mode:
    // Sort candidates by priority, then greedily place non-overlapping labels.
    // Estimate label bounding box: ~6px per char wide, 18px tall.
    const LH = 18, CPW = 6, PAD = 4;
    const placed = [];   // {x1,y1,x2,y2} of already-placed global labels

    function overlaps(sx, sy, w) {
      const x1 = sx - w/2, y1 = sy - LH - PAD, x2 = sx + w/2, y2 = sy;
      return placed.some(r => x1 < r.x2 && x2 > r.x1 && y1 < r.y2 && y2 > r.y1);
    }

    // Priority order for collision check: hovered/selected > Interview > fit desc
    const priority = (job) => {
      if (job.id === state.hoveredId || job.id === state.selectedId) return 1000;
      if (job.status === "Interview") return 100 + job.fit;
      return job.fit;
    };
    const sorted = [...JOBS].sort((a, b) => priority(b) - priority(a));

    // Hover-ring labels (isHot + isNearby) are collected here and positioned
    // after a lightweight repulsion pass (Option C) so dense clusters spread out.
    // { el, sx, sy (dot screen pos / ideal anchor), cx, cy (current label pos), lw }
    const ringLabels = [];

    sorted.forEach((job) => {
      const label = labelEls.get(job.id);
      if (!label) return;
      // When labels are off, only the actively hovered job gets hot treatment (not selected)
      const isHot    = state.showLabels
        ? (job.id === state.hoveredId || job.id === state.selectedId)
        : (job.id === state.hoveredId);
      const isNearby = nearbyIds.has(job.id);
      const isGlobal = label.classList.contains("visible");

      if (!isHot && !isNearby && !isGlobal) { label.style.opacity = "0"; return; }
      if (!isHot && !isNearby && zoomOpacity <= 0) { label.style.opacity = "0"; return; }

      const v = worldFromJob(job).clone().project(camera);
      if (v.z > 1) { label.style.opacity = "0"; return; }
      const sx = (v.x * 0.5 + 0.5) * width;
      const sy = (-v.y * 0.5 + 0.5) * height;
      const lw = Math.min(170, job.label.length * CPW + 16);

      // In global label mode, skip label if it overlaps a higher-priority placed one
      if (isGlobal && !isHot && !isNearby && overlaps(sx, sy, lw)) {
        label.style.opacity = "0"; return;
      }

      label.style.transform = "translate(-50%, -100%)";

      if (isHot || isNearby) {
        // Ideal anchor: just below the dot (matches the old +18 / +12 offset).
        const idealY = sy + (isHot ? 18 : 12);
        // Defer left/top until after the repulsion pass.
        ringLabels.push({ el: label, sx: sx, sy: idealY, cx: sx, cy: idealY, lw: lw, dotX: sx, dotY: sy });
        if (isHot) {
          label.style.opacity = "0.97";
          label.style.background  = "rgba(30,50,90,0.92)";
          label.style.borderColor = "rgba(100,180,255,0.40)";
        } else {
          label.style.opacity = "0.70";
          label.style.background  = "rgba(18,28,50,0.82)";
          label.style.borderColor = "rgba(80,150,220,0.22)";
        }
      } else {
        label.style.left = sx.toFixed(1) + "px";
        label.style.top  = (sy + 12).toFixed(1) + "px";
        label.style.opacity = (zoomOpacity * 0.88).toFixed(2);
        label.style.background  = "rgba(9,13,20,0.78)";
        label.style.borderColor = "rgba(255,255,255,0.10)";
        // Register in placed grid so lower-priority labels avoid it
        placed.push({ x1: sx - lw/2, y1: sy - LH - PAD, x2: sx + lw/2, y2: sy });
      }
    });

    // ---- Option C: hover-ring repulsion + leader lines ----------------------
    // Only the ~6 hover-ring labels (isHot + isNearby) get a lightweight 2D
    // iterative repulsion pass to push overlapping labels apart, with SVG
    // leader lines drawn from each displaced label back to its job dot.
    // The label's left/top is its bottom-centre anchor (translate(-50%,-100%)),
    // so the box spans [cx-lw/2 .. cx+lw/2] x [cy-LABEL_H .. cy] and its centre
    // is (cx, cy - LABEL_H/2).
    const LABEL_H = 20, PAD2 = 6, N_ITER = 8, MAX_DISP = 60;
    if (ringLabels.length) {
      for (let iter = 0; iter < N_ITER; iter++) {
        const fx = new Array(ringLabels.length).fill(0);
        const fy = new Array(ringLabels.length).fill(0);
        for (let i = 0; i < ringLabels.length; i++) {
          for (let k = i + 1; k < ringLabels.length; k++) {
            const a = ringLabels[i], b = ringLabels[k];
            const aw = a.lw + PAD2, bw = b.lw + PAD2;
            const acx = a.cx, acy = a.cy - LABEL_H / 2;
            const bcx = b.cx, bcy = b.cy - LABEL_H / 2;
            const dx = bcx - acx, dy = bcy - acy;
            const overlapX = (aw + bw) / 2 - Math.abs(dx);
            const overlapY = (LABEL_H + PAD2) - Math.abs(dy);
            if (overlapX > 0 && overlapY > 0) {
              // Push apart along the centre-to-centre vector.
              let nx = dx, ny = dy;
              let len = Math.hypot(nx, ny);
              if (len < 0.01) { nx = (Math.random() - 0.5); ny = (Math.random() - 0.5); len = Math.hypot(nx, ny) || 1; }
              nx /= len; ny /= len;
              // Move by half the smaller overlap each, split between the pair.
              const push = Math.min(overlapX, overlapY) * 0.5;
              fx[i] -= nx * push; fy[i] -= ny * push;
              fx[k] += nx * push; fy[k] += ny * push;
            }
          }
        }
        for (let i = 0; i < ringLabels.length; i++) {
          const r = ringLabels[i];
          r.cx += fx[i]; r.cy += fy[i];
          // Clamp displacement from ideal so labels don't wander too far.
          let ddx = r.cx - r.sx, ddy = r.cy - r.sy;
          const dd = Math.hypot(ddx, ddy);
          if (dd > MAX_DISP) { const s = MAX_DISP / dd; r.cx = r.sx + ddx * s; r.cy = r.sy + ddy * s; }
        }
      }

      // Apply final positions and build leader lines for displaced labels.
      let leaderMarkup = "";
      ringLabels.forEach((r) => {
        r.el.style.left = r.cx.toFixed(1) + "px";
        r.el.style.top  = r.cy.toFixed(1) + "px";
        const disp = Math.hypot(r.cx - r.sx, r.cy - r.sy);
        if (disp > 8) {
          leaderMarkup += '<line x1="' + r.cx.toFixed(1) + '" y1="' + r.cy.toFixed(1) +
            '" x2="' + r.dotX.toFixed(1) + '" y2="' + r.dotY.toFixed(1) +
            '" stroke="rgba(150,180,255,0.35)" stroke-width="1" stroke-dasharray="3 3" />';
        }
      });
      if (leaderSvg) leaderSvg.innerHTML = leaderMarkup;
    } else if (leaderSvg && leaderSvg.childNodes.length) {
      // No hover ring (e.g. nothing hovered) -> clear any leftover lines.
      leaderSvg.innerHTML = "";
    }
    if (!state.hoveredId && leaderSvg && leaderSvg.childNodes.length) {
      leaderSvg.innerHTML = "";
    }
  }

  function animate(time) {
    requestAnimationFrame(animate);
    syncSceneState(time || 0);
    ringGroup.children.forEach((ring) => { if (ring.userData.billboard) ring.lookAt(camera.position); });
    updateLabels();
    updateAxisLabels();
    updateCoverageLabels();
    if (dirtyMap) renderMapState();
    if (dirtyList) renderListState();
    renderer.render(scene, camera);
  }

  function renderDetail() {
    const job = jobById.get(state.selectedId) || JOBS[0];
    const el = $("#detail");
    if (!job) {
      el.innerHTML = "<h2>No role selected</h2>";
      return;
    }
    const stars = "★".repeat(job.fit) + "☆".repeat(5 - job.fit);
    const salRange = (job.sal_min && job.sal_max && job.sal_min !== job.sal_max)
      ? "$" + job.sal_min + "K - $" + job.sal_max + "K"
      : "$" + job.sal + "K";
    const submitted = job.date ? fmtDate(job.date) : "-";
    const hasOutcome = jobOutcomes.has(job.id);
    const outcome = jobOutcomes.get(job.id) || "pending";
    el.innerHTML =
      "<h2>" + escapeHtml(job.label) + "</h2>" +
      "<div class=\"org\">" + escapeHtml(job.org) + " | " + escapeHtml(job.place) + "</div>" +
      "<div class=\"chips\">" +
      "<span class=\"chip\">Status: " + escapeHtml(job.status) + "</span>" +
      "<span class=\"chip\">Fit: " + stars + " (" + job.fit + "/5)</span>" +
      "<span class=\"chip\">P(int): " + job.p + "%</span>" +
      "<span class=\"chip\">Salary: $" + job.sal + "K</span>" +
      "<span class=\"chip\">Range: " + salRange + "</span>" +
      "<span class=\"chip\">Submitted: " + escapeHtml(submitted) + "</span>" +
      (hasOutcome
        ? "<button class=\"chip outcome-chip\" data-action=\"cycle-outcome\" data-job-id=\"" + job.id +
          "\" title=\"Click to cycle outcome\" style=\"color:" + OUTCOME_COLORS[outcome] + ";cursor:pointer\">Outcome: " + escapeHtml(outcome) + "</button>"
        : "") +
      "</div>" +
      "<div class=\"note\">" + escapeHtml(job.note || "No note recorded.") + "</div>";
  }

  function renderRoleList() {
    const list = $("#role-list");
    list.innerHTML = "";
    JOBS.forEach((job) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "role-row";
      row.dataset.jobId = job.id;
      row.innerHTML =
        "<div class=\"role-line\"><span>" + escapeHtml(job.label) + "</span><span>" + job.fit + "/5</span></div>" +
        "<div class=\"role-meta\">" + escapeHtml(job.org) + " | " + escapeHtml(job.status) + " | " + escapeHtml(job.place) + "</div>";
      row.addEventListener("mouseenter", () => setHover(job.id));
      row.addEventListener("mouseleave", () => setHover(null));
      row.addEventListener("click", () => selectJob(job.id));
      list.appendChild(row);
    });
  }

  function renderListState() {
    $$(".role-row").forEach((row) => {
      const id = row.dataset.jobId;
      row.style.display = visibleIds.has(id) ? "" : "none";
      row.classList.toggle("hot", id === state.hoveredId);
      row.classList.toggle("selected", id === state.selectedId);
    });
    dirtyList = false;
  }

  // ── Map view boxes per tier ────────────────────────────────────────────────
  const VIEWBOX = {
    countries: "0 0 1608 1180",
    CA: "0 0 1608.4 644",
    US: "0 0 1608 1180",
  };

  // ── Tier 1: simplified North America country outlines (countries viewBox) ───
  // Two approximate, clearly-labelled regions sitting in the Canada viewBox space.
  const COUNTRY_SHAPES = [
    { code: "CA", name: "Canada",
      d: "M40,40 L1560,40 L1560,300 L1180,300 L1120,360 L820,420 L460,420 L120,300 Z",
      lx: 700, ly: 200 },
    { code: "US", name: "United States",
      d: "M120,300 L460,420 L820,420 L1120,360 L1180,300 L1560,300 L1560,604 L120,604 Z",
      lx: 700, ly: 500 },
  ];

  // ── Tier 2 (US): real state polygons (EHT projection, combined NA viewBox) ──
  // Python-generated from build_us_state_paths() — same equirectangular
  // projection as the Canada province paths, so they line up in "0 0 1608 1180".
  // Alaska + Hawaii are fixed insets in the lower-left of that viewBox.

  // Real province SVG paths from EHT/canadaGeo.ts (viewBox 1608.4 × 644)
  const CANADA_PROVINCE_PATHS = [
    {name:"Quebec",abr:"QC",d:"M1396.8,394.3L1426.5,409.2L1429.7,416.8L1419.7,417.7L1395.1,407.9L1378.1,393.6L1388.8,393ZM1514.1,347.2L1486.1,351.3L1479.2,359.1L1479,367.1L1477.4,363.2L1458.4,383.4L1342.7,381.5L1329.6,395.3L1325.3,409.9L1305.9,413.8L1283.2,445.4L1257.7,436.3L1282.3,446.2L1253.5,487.2L1267.4,479.4L1299,438.6L1339,415.9L1358.3,411.7L1376.7,416.2L1384.6,426.8L1377.3,423.1L1384.5,430.8L1381.7,436.9L1364.2,449.1L1352.7,442.9L1325.7,454.3L1307.2,451.8L1307.1,462.7L1295,470.6L1291.5,465.9L1277.6,488.7L1265.7,527.7L1250.8,532.4L1249.7,539.1L1190.4,539.7L1198,533.4L1196.7,522.5L1161,525.8L1138.7,504.9L1117.6,499.4L1104,476.2L1102.3,360.8L1106.1,366.8L1102.3,360.1L1102,343L1107.8,340.5L1115,354.7L1114.2,347.7L1117.9,345L1111.6,336.3L1123.1,322.4L1116.5,312.7L1117.9,303.2L1112.5,298.9L1114.1,291.6L1110.1,284.5L1113.7,282.8L1109.4,278.5L1114,275.1L1106.9,267.1L1111.3,264.1L1105.2,263.8L1102.6,252L1098.2,249.9L1134.9,231L1157.3,200.7L1157.5,176.5L1152.4,159.6L1140.7,144L1120.1,131.3L1120,120.9L1124.3,122.3L1136.3,107.9L1132.1,107.2L1134.7,98.4L1143.1,102.8L1138.9,99L1143.5,95.9L1141,92.3L1153.3,84.9L1137.3,87.8L1141.4,85.8L1135.3,77L1141.3,73.4L1133.6,70.5L1139.5,64.6L1127,66.1L1136.1,53.7L1134.3,46.1L1140.2,43.5L1130.4,37.8L1127.7,21.4L1141.2,12.1L1173.7,21L1169.2,25L1179.7,20.4L1193.7,26.6L1190.6,22.4L1209.8,15.4L1229.1,26.3L1226.1,34.7L1236.9,33.8L1240.8,39.5L1235.1,42.7L1248.5,41.6L1242.7,46.8L1248.3,47.5L1243.9,48.6L1248.4,55.1L1274.7,57.2L1278.7,65.5L1286.3,57.6L1288.9,65.4L1280.5,74L1284.2,87.7L1258.4,87.9L1285.4,93.7L1281.8,110.1L1291.4,112.5L1285.8,114.7L1289.4,117L1285.7,125.5L1279.8,118.1L1281.1,124.8L1272.8,126.6L1280.8,132L1293.3,122.6L1307.5,126.5L1310.5,133.5L1307.7,145.9L1288.9,156.7L1306.6,148.5L1314,132.4L1316.7,140.2L1311.7,147.5L1319,135.8L1319.4,152L1323.6,141.5L1339.4,135.1L1342.2,125.1L1352,131.5L1349.6,140.1L1353.9,132.5L1348.9,126.5L1354.5,124.3L1350.9,122.7L1353,119.4L1363.3,118.5L1356,115.2L1358.7,108.4L1362.6,111.4L1359.2,105L1369.4,108.4L1359.2,97.6L1369.4,96.8L1364.9,93.1L1370,82L1377.7,80.6L1371.8,81.9L1376.5,86.4L1370.8,88.3L1375.5,91.8L1372.3,103.8L1381.2,104.8L1377.7,113.8L1382.1,119.2L1371.4,121.9L1397,127.2L1386.5,129.4L1390.8,135.5L1379.6,147.1L1386.4,156.6L1394.9,157.6L1389.8,183.3L1385.1,188.3L1389.8,196.5L1385,200.5L1389.7,203.1L1387.1,207.4L1397.7,209L1392.7,213.9L1404.1,229.1L1396.3,234.1L1393.6,251.3L1356.5,248.2L1336.5,229.5L1338,247.4L1324.6,237.5L1331.8,251L1321.4,252.6L1323.5,262.6L1318.1,267.7L1324.5,276.3L1323.4,281.5L1334.1,289.4L1331.2,308.6L1338.5,307.8L1342,298.6L1345.8,303.3L1342.7,323.6L1345.7,320.2L1354.4,328.3L1367.1,324.5L1376.7,334.7L1376.8,342.8L1385.4,325L1384.3,304.1L1393.1,296.2L1398.9,310.1L1386,315.5L1393.8,325.8L1392.1,329.6L1514.1,329.6Z",cx:1300,cy:330},
    {name:"Newfoundland and Labrador",abr:"NL",d:"M1377.7,80.6L1373.5,82.8L1380.6,84.9L1372.3,90.1L1384.3,88.9L1382.8,97L1388.9,100.1L1385.2,104.1L1392.6,104.3L1386.3,108.2L1398.9,111.2L1386.6,119.1L1403.5,118L1399.9,124L1408.3,128.3L1395,140.7L1414,135.3L1407.6,143.4L1413.5,143.2L1399.6,150.3L1415.9,144.4L1418.5,148.8L1411.8,151.8L1421.9,150.6L1426.3,160.5L1414.2,164.6L1436,177L1425.9,185.8L1429.9,191.1L1415,186.3L1423.3,184.7L1413.4,185.9L1430.5,193.6L1421.6,196.3L1431.7,201L1422.8,201.1L1436.1,203L1434.2,207.9L1438.2,208.4L1433.3,209.4L1447,214.2L1443.7,217.8L1449.9,215.2L1448.4,222.7L1454.7,216L1452.1,229.2L1457.3,227L1448.4,239.8L1465,229.7L1461.6,236.3L1471.4,235.4L1461.9,247.1L1476.3,232.5L1472.2,240.4L1478.8,234.9L1480.8,244.1L1509.6,252.2L1468.7,268.1L1490.6,262.7L1458.5,276.3L1458.4,283.8L1444.8,274.7L1460,284.7L1453.6,291.6L1477.9,279.1L1482.2,271.3L1501.5,267.6L1491.6,266.9L1494.5,262.5L1508.1,264.1L1513.4,271.6L1513.8,277.4L1505.9,281.8L1510.2,282.2L1509.1,286.7L1525.8,276.1L1521,279.4L1534.7,283.3L1529.5,283.4L1538.8,295.5L1531.3,298.7L1537.9,304.4L1531.4,305.8L1539.1,310.3L1525.2,311.8L1538.9,314.7L1538.3,319.6L1530.7,316.5L1541.3,323.1L1517,346.7L1514.1,347.2L1514.1,329.6L1392.1,329.6L1393.8,325.8L1386,315.5L1398.9,310.1L1393.1,296.2L1384.3,304.1L1385.4,325L1376.8,342.8L1376.7,334.7L1367.1,324.5L1354.4,328.3L1345.7,320.2L1342.7,323.6L1344.4,300.4L1331.2,308.6L1334.1,289.4L1323.4,281.5L1324.5,276.3L1318.1,267.7L1323.5,262.6L1321.4,252.6L1331.8,251L1324.6,237.5L1338,247.4L1336.5,229.5L1356.5,248.2L1393.6,251.3L1396.3,234.1L1404.1,229.1L1392.7,213.9L1397.7,209L1387.1,207.4L1389.7,203.1L1384.4,196.8L1389.8,196.5L1385.1,188.3L1389.8,183.3L1394.9,157.6L1386.4,156.6L1379.6,147.1L1390.8,135.5L1386.5,129.4L1397,127.2L1371.4,121.9L1382.1,119.2L1377.7,113.8L1381.2,104.8L1372.3,103.8L1375.5,91.8L1370.8,88.3L1376.5,86.4L1371.8,81.9ZM1536.6,363.7L1532.5,368L1531.5,363L1532.3,370L1525.1,378.1L1518.6,403.2L1532.2,385L1530.9,391.8L1544.2,390.8L1534.3,397.1L1531.2,402.2L1537.4,398.9L1532,406.8L1545.9,404.4L1547.1,410.2L1550.2,403.3L1545.6,418.3L1562.8,403.2L1562.1,411.7L1570.3,405.1L1581,412L1567.8,425.5L1578.4,429L1568,438L1589.8,431.5L1572.1,444.6L1578.3,448.1L1572.3,454L1577.2,463.8L1584,449.5L1592.5,446.6L1584.5,461.3L1587.1,467.1L1593.4,455.4L1595.7,459.8L1590.5,485.8L1578,490.2L1579.1,473.4L1567.5,484.8L1574.6,466.7L1566.2,452.5L1563.6,466L1559.8,468.6L1563.4,461.4L1555.8,466.9L1545.6,483.5L1534.6,480.9L1558.2,459.6L1546.1,457.7L1541.9,467.5L1535.7,466.3L1539,461.9L1532.4,465.6L1541.1,459.3L1535.8,459.8L1538.5,450.8L1533.3,458.6L1531.4,454.5L1531.4,460.5L1520,463.7L1492.6,457L1473.7,461.2L1471.9,452.3L1492.7,434L1475.1,433.6L1483.4,426.2L1480,431.1L1484.6,432.4L1491.2,415L1499.6,420.1L1495,415.9L1500.4,414.1L1495.9,415L1498.9,412.3L1493.5,407.8L1503.2,405.6L1498.6,399.3L1509.1,371.8L1513.2,371.1L1508.7,368.8L1517.3,362.1L1514.3,359L1521.7,349.5L1543.2,341.5L1541.7,350.5L1532.8,348.5L1539.6,354.4L1537.2,362.4Z",cx:1460,cy:190},
    {name:"British Columbia",abr:"BC",d:"M123.2,281.6L119,276L119.8,264.4L128.8,266.1L127.3,271.4L136.4,269.5L135.2,276.2L127.2,279.2L132.9,279.6L130.8,282.5L136.5,278.6L136.1,268.4L145.7,264.8L141,289L135.9,294.8L126.5,291.9L132,289.7L121.1,282ZM156.3,323L152.7,326L135,304.8L133.1,301.3L137.3,299.7L129.2,296.9L143.1,292.1L146.8,298.5L139.4,298.1L146.5,301.8L139.7,303.2L145.8,305.6L142.3,308.3L154.4,322.7ZM228.9,394L229.5,385.3L214.5,385.9L217.5,382.3L214.2,375.7L222.9,378.4L220.7,374.2L223.5,372.3L211.8,376.1L205.1,366.5L211.6,363.4L259.9,380.2L271.7,405.6L287,412.7L294.7,433.6L297.2,429.1L299.5,436L293.8,440.5L265.7,427.6L271.4,412.3L269.6,419.5L259,422L251.7,416.9L256.7,413.2L254,415.1L253.6,408.6L249.1,411.5L251.2,406.5L238.9,407.3L239.1,402L247.6,399.2L232.2,393.7ZM414.1,419.5L303.9,419.5L300,411.3L307.3,406.4L299.6,409.6L301.6,398.6L294.7,408.1L284.9,400.5L287.3,397.3L290.4,404.4L294.7,398.5L287.5,396.6L289.5,385L286.5,383.1L289.7,386.5L287.5,394.8L281.2,397.3L272.6,390.8L273.1,379.7L279.8,374.5L266.4,379.9L270.6,361.5L264.7,377.2L257.3,375.8L259.9,368.1L255,376.7L244.4,374.3L254.9,369.2L258.6,361.6L256.2,356.7L256,366L250.6,369.1L239.3,364.5L246.4,361.5L240,357.4L237.3,363.5L223.8,361.8L221.9,356.6L236.4,359.5L237.5,355.1L216.6,354.6L228.5,350L216.7,349.6L221.9,341.2L238.4,338.2L223.3,339.6L224.7,333.7L219.3,338.6L222.6,339.5L219.4,345.8L215,339.4L215.2,332.6L228,320.2L237.2,330.1L232.2,320.5L236,318.2L227.7,318.2L231.7,304.7L219.9,320.7L215.4,323.4L215.2,314.4L211.7,317.7L215,312.2L205.5,320.8L212.3,302.2L204.7,304.9L203.9,295.3L194.9,283L215.2,292.4L197.8,280.9L204.1,274.6L200.1,272.9L201.6,268.7L194.3,272.8L188.7,288.2L174.2,271.2L175.2,265L181.2,271.1L177.4,264.1L185.8,262.5L173.8,265L171.5,257.6L167.2,258.7L168.4,250.7L176.8,259.8L169.3,249.6L178.3,251.2L172.9,244.2L183,239.7L176.1,239.1L185.8,225.5L181.4,227.3L179.5,220.8L180.1,229L174,239.7L177.1,231.2L172.9,217L174.4,206.1L142.6,191.7L113.1,135.9L85.2,111.3L84,102.7L75.6,95.7L59.6,101.6L55.2,114.8L39,122.5L36.7,112.5L12,89.8L267.8,89.6L359.9,90.1L359.6,275.4L364.5,280.6L361.4,284L382.4,295.9L392.2,318.6L396.2,314.9L400.7,323.6L408.8,324.1L416.2,338.3L420.9,335.7L428.2,350.1L455.6,378.8L456.2,401.3L468.6,419.5L431.9,419.5Z",cx:260,cy:310},
    {name:"New Brunswick",abr:"NB",d:"M1295,470.6L1307.1,462.7L1307.2,451.8L1311.9,449.4L1325.7,454.3L1344.2,447.3L1354.6,452.8L1357.5,460.9L1372.4,455.2L1375.1,457.4L1370.8,468.9L1362.3,476.9L1372.8,477.1L1370.9,484L1377.2,502.9L1391.6,505.8L1378.6,517.8L1373.6,506.8L1375.7,517.9L1355.6,532.1L1348.5,530.3L1350.7,525.6L1342.7,537.3L1326.1,535.8L1324.3,521.7L1317.7,519.1L1317.9,477.7L1309.8,468.9L1295,471.8Z",cx:1340,cy:492},
    {name:"Nova Scotia",abr:"NS",d:"M1450,503.6L1440.5,510.8L1447.4,508L1439.9,518.6L1447.4,519.2L1453.6,509.6L1446.5,511.1L1454.5,500.2L1464.4,504.6L1461.6,508.9L1464.2,511.6L1448.6,522.5L1437.3,523.2L1432.5,508.7L1450,478.5L1455.4,484.4L1450.1,501.8ZM1386.7,509.7L1400.4,517.8L1411.8,516.4L1410.5,521.1L1425.7,512.9L1426.4,518.9L1438.3,524.4L1434.2,529.2L1443.1,531.4L1408.8,548.1L1393.8,548L1394.3,556.4L1388.7,554L1389.6,548.7L1386,555.4L1381.9,552.6L1382.7,561.3L1379.6,559.3L1368.7,578.2L1363,576.4L1360.3,585.5L1347.7,573.5L1348.6,559.3L1353.7,552.2L1347.3,556.7L1378.5,529.4L1384.6,540.1L1384.7,533.7L1399.2,528.6L1370.3,529.7L1384.6,510.4Z",cx:1410,cy:535},
    {name:"Saskatchewan",abr:"SK",d:"M690,89.7L690,214.7L701.6,419.5L543.1,419.5L543.1,89.9L648.3,89.7Z",cx:622,cy:260},
    {name:"Alberta",abr:"AB",d:"M468.6,419.5L456.2,401.3L457.6,387.6L451.1,372.3L439.5,363.9L420.9,335.7L416.2,338.3L408.8,324.1L400.7,323.6L396.2,314.9L392.2,318.6L382.4,295.9L361.4,284L364.5,280.6L359.6,275.4L359.9,90.1L543.1,89.9L543.1,419.5L503,419.5Z",cx:450,cy:260},
    {name:"Prince Edward Island",abr:"PE",d:"M1387.7,497.7L1386.2,490.4L1379.8,489L1387.5,477.6L1388.6,495.2L1424.7,495.8L1413.5,502.5L1415.8,509.3L1405.3,507.6L1406.5,499.9L1401,505.3L1388.8,496.7Z",cx:1403,cy:494},
    {name:"Manitoba",abr:"MB",d:"M690,89.7L822.1,89.7L824.8,109.2L818.6,118.1L829.1,128.2L833.1,125.6L830.2,143.1L833.6,126.6L852.4,127.6L865.9,169.5L857.5,182.4L891.9,171.8L925.3,183.6L815.7,304.8L815.6,419.5L701.6,419.5L690,214.7L690,92.1Z",cx:790,cy:290},
    {name:"Ontario",abr:"ON",d:"M1102.3,360.8L1101.6,466.2L1113.1,494.1L1152.5,513.5L1161,525.8L1192.1,520.4L1196.7,522.5L1198,533.4L1167.7,557.9L1149.2,567.3L1138.6,565.8L1151.7,565.9L1146.4,573.8L1136,568.2L1110.5,574.6L1097.9,589.8L1110.8,591.4L1113.5,602.1L1090.1,605.7L1085.5,611L1091.7,613.2L1069.3,609.9L1047.8,632L1036.5,627.3L1038.2,620L1049.3,618.8L1045.4,613L1048.4,602.5L1061.8,589L1061.8,566.9L1070.5,550.9L1062.7,531.5L1076.4,540.5L1073,546.7L1077.4,545.7L1076.5,551.6L1081.9,547.7L1092.2,555.4L1091.9,544.9L1100.1,546.9L1080.1,511.8L1010.9,495L1010.4,484.7L1013.9,483L1006.1,480L1009.8,470.8L1001.5,461.2L1004.9,451L986.2,449.9L975.7,426.2L942.2,419.7L943.2,431.3L936.7,436.6L941.2,426.7L938.2,423.9L933.4,438.4L929.7,440.1L933,432.1L926.1,435L922.4,446L912.1,449.7L894.4,441.9L881.4,448.2L872.9,438.8L866.8,442.9L856.2,430.7L840.9,434.2L824.1,426.2L821.6,409.6L815.7,408.4L815.7,304.8L925.3,183.6L947.4,196.5L954,209.6L999.7,229.2L994.3,239.9L1002,230.7L1050.8,234.7L1053.5,244.3L1049.1,263.3L1054.7,275.6L1055,291.4L1051.6,300.8L1066.7,320.5L1059.2,324L1066.2,322.6L1082.8,338.2L1086,348.7L1075.2,358.7L1086.6,349.4L1099.6,358.2Z",cx:970,cy:410},
  ];

  // Index US state polygons by abbreviation (centroids reused by the dot anchor).
  const US_STATE_BY_ABR = new Map(US_STATE_PATHS.map((s) => [s.abr, s]));

  // ── Map rendering — dispatches on state.mapTier ─────────────────────────────
  // renderMap() fully rebuilds the SVG for the current tier and is re-called on
  // every tier change. renderMapState() only updates highlight/dot styling.
  function renderMap() {
    const svg = $("#location-map");
    svg.setAttribute("viewBox", VIEWBOX[state.mapTier] || VIEWBOX.countries);
    if (state.mapTier === "countries") buildCountryMap(svg);
    else if (state.mapTier === "US") buildUsMap(svg);
    else buildCanadaMap(svg);
    bindMapEvents(svg);
  }

  function buildCountryMap(svg) {
    // Tier-1: use the REAL province/state shapes grouped by country.
    // Clicking anywhere on a country's actual shape enters tier-2.
    const parts = [];
    const caCount = JOBS.filter(j => jobCountry(j) === "CA").length;
    const usCount = JOBS.filter(j => jobCountry(j) === "US").length;

    // Canada — all province paths, each with data-country=CA
    CANADA_PROVINCE_PATHS.forEach(({ d }) => {
      parts.push("<path class=\"country ca\" data-country=\"CA\" data-name=\"Canada (" + caCount + " applications)\" d=\"" + d + "\"></path>");
    });
    parts.push("<text class=\"country-label\" x=\"560\" y=\"340\" text-anchor=\"middle\">Canada</text>");

    // US — all state paths, each with data-country=US
    US_STATE_PATHS.forEach(({ d }) => {
      parts.push("<path class=\"country us\" data-country=\"US\" data-name=\"United States (" + usCount + " applications)\" d=\"" + d + "\"></path>");
    });
    parts.push("<text class=\"country-label\" x=\"700\" y=\"820\" text-anchor=\"middle\">United States</text>");

    svg.innerHTML = parts.join("");
  }

  function buildCanadaMap(svg) {
    const parts = [];
    // Build province job count map
    const provCounts = {};
    JOBS.forEach(j => { if (j.province) provCounts[j.province] = (provCounts[j.province] || 0) + 1; });
    CANADA_PROVINCE_PATHS.forEach(({ abr, name, d, cx, cy }) => {
      const n = provCounts[abr] || 0;
      const label = name + (n > 0 ? " — " + n + " application" + (n === 1 ? "" : "s") : "");
      parts.push("<path class=\"province\" data-province=\"" + abr + "\" data-name=\"" + label + "\" d=\"" + d + "\"></path>");
      parts.push("<text class=\"province-label\" x=\"" + cx + "\" y=\"" + (cy + 4) + "\" text-anchor=\"middle\">" + abr + "</text>");
      parts.push("<path class=\"province-hit\" data-province=\"" + abr + "\" data-name=\"" + label + "\" d=\"" + d + "\" fill=\"transparent\" cursor=\"pointer\"></path>");
    });
    JOBS.forEach((job) => {
      if (jobCountry(job) !== "CA") return;
      const p = provinceAnchor(job);
      if (!p) return;
      parts.push("<circle class=\"map-dot\" data-job-id=\"" + job.id + "\" cx=\"" + p.x + "\" cy=\"" + p.y + "\" r=\"6\" fill=\"" + colorFor(job) + "\"></circle>");
    });
    svg.innerHTML = parts.join("");
  }

  function buildUsMap(svg) {
    const parts = [];
    const stateCounts = {};
    JOBS.forEach(j => { if (j.province) stateCounts[j.province] = (stateCounts[j.province] || 0) + 1; });
    US_STATE_PATHS.forEach(({ abr, name, d, cx, cy }) => {
      const n = stateCounts[abr] || 0;
      const label = name + " (" + abr + ")" + (n > 0 ? " — " + n + " application" + (n === 1 ? "" : "s") : "");
      parts.push("<path class=\"usstate\" data-province=\"" + abr + "\" data-name=\"" + label + "\" d=\"" + d + "\"></path>");
      parts.push("<text class=\"usstate-label\" x=\"" + cx + "\" y=\"" + (cy + 4) + "\" text-anchor=\"middle\">" + abr + "</text>");
    });
    JOBS.forEach((job) => {
      if (jobCountry(job) !== "US") return;
      const p = usStateAnchor(job);
      if (!p) return;
      parts.push("<circle class=\"map-dot\" data-job-id=\"" + job.id + "\" cx=\"" + p.x + "\" cy=\"" + p.y + "\" r=\"6\" fill=\"" + colorFor(job) + "\"></circle>");
    });
    svg.innerHTML = parts.join("");
  }

  // Re-bind delegated map events after each full rebuild (innerHTML wipes nodes).
  let mapEventsBound = false;
  // Tier-1 single/double click disambiguation: a first click arms a 280ms timer
  // (single = filter only); a second click within the window drills into tier-2.
  let pendingClickTimer = null;
  const DOUBLE_CLICK_MS = 280;

  function bindMapEvents() {
    if (mapEventsBound) return;
    mapEventsBound = true;
    const svg = $("#location-map");

    svg.addEventListener("mousemove", (ev) => {
      const dot = ev.target.closest(".map-dot");
      if (dot) { setHover(dot.dataset.jobId, ev); hideHoverLabel(); return; }
      const region = ev.target.closest("[data-name]");
      if (region) {
        // Tier-1: highlight the whole country group, not just the single path
        $$(".country").forEach(el => el.classList.remove("country-hover"));
        if (region.dataset.country) {
          $$("[data-country='" + region.dataset.country + "']").forEach(el => el.classList.add("country-hover"));
        }
        showHoverLabel(region, ev); return;
      }
      $$(".country").forEach(el => el.classList.remove("country-hover"));
      // Empty space inside the SVG: don't hide here — the popup is offset toward
      // empty space, so hiding on every gap pixel makes the axis buttons
      // unreachable. The popup hides on svg mouseleave / popup mouseleave below.
    });
    svg.addEventListener("mouseleave", (ev) => {
      setHover(null);
      // Keep the popup if the cursor is moving INTO the popup (to click buttons).
      const into = ev.relatedTarget;
      if (into && into.closest && into.closest("#map-hover-label")) return;
      hideHoverLabel();
    });
    // Hide once the cursor leaves the popup itself (unless going back onto the map).
    $("#map-hover-label").addEventListener("mouseleave", (ev) => {
      const into = ev.relatedTarget;
      if (into && into.closest && into.closest("#location-map")) return;
      hideHoverLabel();
    });
    svg.addEventListener("click", (ev) => {
      const dot = ev.target.closest(".map-dot");
      if (dot) { selectJob(dot.dataset.jobId); return; }
      if (state.mapTier === "countries") {
        const c = ev.target.closest("[data-country]");
        if (!c) return;
        const code = c.dataset.country;
        if (pendingClickTimer) {
          // second click within window → double-click → drill into tier-2
          clearTimeout(pendingClickTimer);
          pendingClickTimer = null;
          enterCountryTier(code);
        } else {
          // first click → arm timer; single click only filters to this country
          pendingClickTimer = setTimeout(() => {
            pendingClickTimer = null;
            state.filters.country = code;  // single click sets; use Select All to clear
            dirtyFilter = true; dirtyMap = true;
          }, DOUBLE_CLICK_MS);
        }
        return;
      }
      // tier 2 — single click toggles province/state filter
      const hit = ev.target.closest("[data-province]");
      if (hit) {
        const p = hit.dataset.province;
        if (state.filters.province instanceof Set) {
          if (state.filters.province.has(p)) state.filters.province.delete(p);
          else state.filters.province.add(p);
        } else { state.filters.province = new Set([p]); }
        dirtyFilter = true; dirtyMap = true;
      }
    });
  }

  function enterCountryTier(code) {
    state.mapTier = code;
    state.filters.country = code;   // selecting a country filters to all its jobs
    state.filters.province = new Set();
    dirtyFilter = true;
    renderMap();
    dirtyMap = true;
  }

  function mapBack() {
    state.mapTier = "countries";
    state.filters.country = null;
    state.filters.province = new Set();
    dirtyFilter = true;
    renderMap();
    dirtyMap = true;
  }

  // Jobs of the region under the pointer — held in a closure so the pie axis
  // switcher can re-render the chart without re-triggering the hover.
  let lastHoveredJobs = [];
  let lastHoveredName = "";

  // 5 fixed segment colours for the pie (red→blue, matches FIT_COLORS intent).
  const PIE_COLORS = FIT_COLORS;

  // Jobs that belong to the hovered region (country in tier-1, province/state in
  // tier-2), restricted to currently-visible jobs.
  function regionJobs(region) {
    if (region.dataset.country) {
      const c = region.dataset.country;
      return JOBS.filter((j) => jobCountry(j) === c && visibleIds.has(j.id));
    }
    if (region.dataset.province) {
      const p = region.dataset.province;
      return JOBS.filter((j) => j.province === p && visibleIds.has(j.id));
    }
    return [];
  }

  // Build a 70x70 SVG pie of the level distribution (1..5) for one axis.
  function buildPie(jobs, axis) {
    const SIZE = 70, R = 33, CX = 35, CY = 35;
    if (!jobs || jobs.length === 0) {
      return "<svg width=\"" + SIZE + "\" height=\"" + SIZE + "\" viewBox=\"0 0 " + SIZE + " " + SIZE + "\">" +
        "<circle cx=\"" + CX + "\" cy=\"" + CY + "\" r=\"" + R + "\" fill=\"#1a2233\" stroke=\"rgba(230,240,255,0.2)\"></circle>" +
        "<text x=\"" + CX + "\" y=\"" + (CY + 3) + "\" text-anchor=\"middle\" fill=\"#8ea0bd\" font-size=\"8\">0</text></svg>";
    }
    const buckets = [0, 0, 0, 0, 0];
    jobs.forEach((j) => {
      const v = clamp(Math.round(j[axis]), 1, 5);
      buckets[v - 1]++;
    });
    const total = buckets.reduce((a, b) => a + b, 0);
    let start = -Math.PI / 2;  // start at 12 o'clock
    const segs = [];
    buckets.forEach((count, i) => {
      if (count === 0) return;
      const frac = count / total;
      const end = start + frac * Math.PI * 2;
      if (frac >= 0.9999) {
        // single full segment — a wedge path can't draw 360°, use a circle
        segs.push("<circle cx=\"" + CX + "\" cy=\"" + CY + "\" r=\"" + R + "\" fill=\"" + PIE_COLORS[i] + "\"></circle>");
      } else {
        const x1 = CX + R * Math.cos(start), y1 = CY + R * Math.sin(start);
        const x2 = CX + R * Math.cos(end), y2 = CY + R * Math.sin(end);
        const large = (end - start) > Math.PI ? 1 : 0;
        segs.push("<path d=\"M" + CX.toFixed(1) + "," + CY.toFixed(1) +
          " L" + x1.toFixed(2) + "," + y1.toFixed(2) +
          " A" + R + "," + R + " 0 " + large + " 1 " + x2.toFixed(2) + "," + y2.toFixed(2) +
          " Z\" fill=\"" + PIE_COLORS[i] + "\"></path>");
      }
      start = end;
    });
    return "<svg width=\"" + SIZE + "\" height=\"" + SIZE + "\" viewBox=\"0 0 " + SIZE + " " + SIZE + "\">" +
      segs.join("") +
      "<circle cx=\"" + CX + "\" cy=\"" + CY + "\" r=\"" + R + "\" fill=\"none\" stroke=\"rgba(5,8,12,0.6)\" stroke-width=\"1\"></circle></svg>";
  }

  function showHoverLabel(region, ev) {
    lastHoveredJobs = regionJobs(region);
    lastHoveredName = region.dataset.name || "";
    renderHoverCard();
    $("#map-hover-label").classList.add("show");
    positionHoverLabel(ev);
  }

  const AXIS_BUCKET_LABELS = {
    x: ["","Startup","Innov.org","Nonprofit","Post-sec","Gov"],
    y: ["","Ops","Change","Strategy","Programs","Ecosystem"],
    z: ["","Specialist","Officer","Manager","Director","VP/C"]
  };

  function renderHoverCard() {
    const el = $("#map-hover-label");
    const n = lastHoveredJobs.length;
    const countTxt = n === 0 ? "No jobs in region" : (n + " application" + (n === 1 ? "" : "s"));
    const axis = state.mapPieAxis;
    // Build color legend
    const bucketLabels = AXIS_BUCKET_LABELS[axis] || [];
    let legend = "<span class=\"map-hover-legend\">";
    for (let i = 1; i <= 5; i++) {
      const cnt = lastHoveredJobs.filter(j => Math.round(j[axis]) === i).length;
      if (cnt === 0) continue;
      legend += "<span class=\"legend-item\"><span class=\"legend-dot\" style=\"background:" + PIE_COLORS[i-1] + "\"></span>" +
        "<span class=\"legend-label\">" + (bucketLabels[i] || i) + " (" + cnt + ")</span></span>";
    }
    legend += "</span>";
    el.innerHTML =
      "<span class=\"map-hover-pie\">" + buildPie(lastHoveredJobs, axis) + "</span>" +
      "<span class=\"map-hover-text\">" +
        "<span class=\"map-hover-name\">" + lastHoveredName + "</span>" +
        "<span class=\"map-hover-count\">" + countTxt + "</span>" +
        legend +
      "</span>";
  }

  // Re-render only the pie/active-button styling for the persisted hover region.
  function refreshHoverPie() {
    if (!$("#map-hover-label").classList.contains("show")) return;
    renderHoverCard();
  }

  function hideHoverLabel() {
    $("#map-hover-label").classList.remove("show");
  }

  function positionHoverLabel(ev) {
    const el = $("#map-hover-label");
    if (!ev) { hideHoverLabel(); return; }
    const rect = $("#map-overlay").getBoundingClientRect();
    el.style.left = (ev.clientX - rect.left + 12) + "px";
    el.style.top = (ev.clientY - rect.top + 12) + "px";
  }

  function provinceAnchor(job) {
    // Centroids in the 1608.4×644 viewBox coordinate space
    const anchors = {
      BC:[260,310], AB:[450,260], SK:[622,260], MB:[790,290],
      ON:[970,410], QC:[1300,330], NB:[1340,492], NS:[1410,535],
      PE:[1403,494], NL:[1460,190],
    };
    const a = anchors[job.province];
    if (!a) return null;
    return spiralAround(a[0], a[1], job.provinceOrdinal || 1);
  }

  function usStateAnchor(job) {
    const s = US_STATE_BY_ABR.get(job.province);
    if (!s) return null;
    return spiralAround(s.cx, s.cy, job.provinceOrdinal || 1);
  }

  function spiralAround(x, y, n) {
    const ring = Math.ceil((Math.sqrt(n) - 1) / 2);
    const angle = n * 2.399963;
    const radius = 10 + ring * 12;
    return { x: x + Math.cos(angle) * radius, y: y + Math.sin(angle) * radius };
  }

  function renderMapState() {
    $("#map-overlay").classList.toggle("open", state.showMap);
    const isTier1 = state.mapTier === "countries";
    $("#map-back").classList.toggle("show", !isTier1);
    // Select All / Deselect All are always shown (they act on the active tier).
    $("#map-select-all").classList.add("show");
    $("#map-deselect-all").classList.add("show");
    const titles = { countries: "Select a country", CA: "Canada - provinces", US: "United States - states" };
    $("#map-title").textContent = titles[state.mapTier] || "Location map";

    // province filter is a Set; deselect-all uses "__none__" sentinel
    const provSet = state.filters.province instanceof Set ? state.filters.province : new Set();
    const provDeselectAll = state.filters.province === "__none__";
    const hasProvFilter = provSet.size > 0 || provDeselectAll;
    const activeCountry = state.filters.country;
    $$(".country").forEach((el) => {
      const c = el.dataset.country;
      const off = activeCountry === "__none__" || (activeCountry && c !== activeCountry);
      el.style.opacity = off ? "0.4" : "1";
    });
    $$(".province, .usstate").forEach((el) => {
      const p = el.dataset.province;
      const isSelected = !provDeselectAll && hasProvFilter && provSet.has(p);
      const isDimmed = hasProvFilter && !isSelected;
      el.style.opacity = isDimmed ? "0.28" : "1";
      el.style.stroke = isSelected ? "rgba(96,165,250,0.9)" : "";
      el.style.strokeWidth = isSelected ? "2.5" : "";
    });
    $$(".map-dot").forEach((dot) => {
      const id = dot.dataset.jobId;
      const job = jobById.get(id);
      dot.setAttribute("fill", job ? colorFor(job) : "#d1d5db");
      dot.classList.toggle("dim", !visibleIds.has(id));
      dot.classList.toggle("hot", id === state.hoveredId || id === state.selectedId);
    });
    dirtyMap = false;
  }

  function syncControls() {
    $("#job-count").textContent = JOBS.length + " roles";
    $("#sx").value = state.focus.sx;
    $("#sy").value = state.focus.sy;
    $("#sz").value = state.focus.sz;
    $("#radius").value = state.focus.radius;
    $("#boundary").value = state.focus.boundary;
    updateFocusLabels();
    updateFilterLabels();
    updateTimelineLabels();
  }

  function updateFocusLabels() {
    const f = state.focus;
    $("#sx-value").textContent = f.sx.toFixed(1) + " " + axisName("x", f.sx);
    $("#sy-value").textContent = f.sy.toFixed(1) + " " + axisName("y", f.sy);
    $("#sz-value").textContent = f.sz.toFixed(1) + " " + axisName("z", f.sz);
    $("#radius-value").textContent = "+/-" + f.radius.toFixed(1);
    $("#boundary-value").textContent = BOUNDARY_LABELS[f.boundary];
    $("#axis-readout").textContent = "X " + axisName("x", f.sx) + " | Y " + axisName("y", f.sy) + " | Z " + axisName("z", f.sz) + " | " + BOUNDARY_LABELS[f.boundary];
  }

  function axisName(axis, value) {
    return AXIS_LABELS[axis][clamp(Math.round(value), 1, 5)];
  }

  function updateFilterLabels() {
    $("#fit-floor-value").textContent = state.filters.fitFloor + "/5";
    const lo = Math.min(state.filters.salaryMin, state.filters.salaryMax);
    const hi = Math.max(state.filters.salaryMin, state.filters.salaryMax);
    $("#salary-range-value").textContent = "$" + lo + "K – $" + hi + "K";
    const fill = $("#salary-fill");
    if (fill) {
      const span = 220 - 55;
      fill.style.left = ((lo - 55) / span * 100).toFixed(1) + "%";
      fill.style.width = ((hi - lo) / span * 100).toFixed(1) + "%";
    }
  }

  function pctToDate(pct) {
    const a = dateMs(minDate), b = dateMs(maxDate);
    return new Date(a + (b - a) * pct / 100).toISOString().slice(0, 10);
  }

  function updateTimelineLabels() {
    const s = state.timeline.startPct, e = state.timeline.endPct;
    $("#tl-start-label").textContent = fmtDate(pctToDate(s));
    $("#tl-end-label").textContent = fmtDate(pctToDate(e));
    const wrap = $(".range-wrap"), fill = $("#timeline-fill");
    if (wrap && fill) {
      const g = trackPx(wrap);
      const x1 = g.off + pctToViewFrac(s) * g.tW;
      const x2 = g.off + pctToViewFrac(e) * g.tW;
      fill.style.left = Math.max(0, x1).toFixed(1) + "px";
      fill.style.right = Math.max(0, g.cW - x2).toFixed(1) + "px";
    }
  }

  function renderTimelineTicks() {
    const box = $("#tl-ticks"); if (!box) return;
    const g = trackPx(box);
    const minMs = dateMs(minDate), fullMs = dateMs(maxDate) - minMs;
    if (fullMs <= 0) { box.innerHTML = ""; return; }
    const loMs = dateMs(pctToDate(vLo)), hiMs = dateMs(pctToDate(vHi));
    const spanD = (hiMs - loMs) / 86400000;
    const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const ticks = [];
    const put = (ms, lbl, cls) => {
      if (ms < loMs - 1 || ms > hiMs + 1) return;
      const x = g.off + pctToViewFrac((ms - minMs) / fullMs * 100) * g.tW;
      ticks.push({ x, lbl, cls: cls || "" });
    };
    if (spanD > 130) {                         // months
      const c = new Date(loMs); c.setDate(1); c.setMonth(c.getMonth() + 1);
      while (c.getTime() <= hiMs) { put(c.getTime(), MONTHS[c.getMonth()] + (c.getMonth() === 0 ? " " + c.getFullYear() : ""), ""); c.setMonth(c.getMonth() + 1); }
    } else if (spanD > 24) {                    // weeks (Mondays)
      const c = new Date(loMs); c.setHours(0, 0, 0, 0); c.setDate(c.getDate() + ((8 - c.getDay()) % 7));
      while (c.getTime() <= hiMs) { put(c.getTime(), MONTHS[c.getMonth()] + " " + c.getDate(), ""); c.setDate(c.getDate() + 7); }
    } else {                                    // days
      const step = spanD > 12 ? 2 : 1;
      const c = new Date(loMs); c.setHours(0, 0, 0, 0); c.setDate(c.getDate() + 1);
      while (c.getTime() <= hiMs) { put(c.getTime(), (c.getDate() === 1 ? MONTHS[c.getMonth()] + " " : "") + c.getDate(), c.getDate() === 1 ? "mstart" : ""); c.setDate(c.getDate() + step); }
    }
    const todayMs = dateMs(DATA.today || maxDate);
    if (todayMs >= loMs && todayMs <= hiMs) put(todayMs, "Today", "today");
    box.innerHTML = ticks.map((t) =>
      "<span class=\"tm " + t.cls + "\" style=\"left:" + t.x.toFixed(1) + "px\"><span class=\"tmk\"></span>" + t.lbl + "</span>"
    ).join("");
  }

  function renderStatusPills() {
    const box = $("#status-pills");
    box.innerHTML = "";
    Object.keys(STATUS_COLORS).forEach((status) => {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "pill";
      pill.dataset.status = status;
      pill.style.color = STATUS_COLORS[status];
      pill.textContent = status;
      pill.addEventListener("click", () => {
        if (state.filters.statuses.has(status)) state.filters.statuses.delete(status);
        else state.filters.statuses.add(status);
        pill.classList.toggle("off", !state.filters.statuses.has(status));
        dirtyFilter = true;
      });
      box.appendChild(pill);
    });
  }

  function resetFilters() {
    state.filters.text = "";
    state.filters.fitFloor = 1;
    state.filters.salaryMin = 55;
    state.filters.salaryMax = 220;
    state.filters.statuses = new Set(Object.keys(STATUS_COLORS));
    state.filters.country = null;          // also reset map filters
    state.filters.province = new Set();
    state.mapTier = "countries";
    $("#filter-text").value = "";
    $("#fit-floor").value = 1;
    $("#salary-min").value = 55;
    $("#salary-max").value = 220;
    $$(".pill").forEach((p) => p.classList.remove("off"));
    updateFilterLabels();
    renderMap();
    dirtyFilter = true; dirtyMap = true;
  }

  function resetTimeline() { setScale(100, 50); }

  function savePreset() {
    const name = $("#preset-name").value.trim();
    if (!name) return;
    const presets = JSON.parse(localStorage.getItem("job-viz-focus-presets") || "{}");
    presets[name] = state.focus;
    localStorage.setItem("job-viz-focus-presets", JSON.stringify(presets));
    $("#preset-name").value = "";
    renderPresets();
  }

  function deletePreset(name) {
    const presets = JSON.parse(localStorage.getItem("job-viz-focus-presets") || "{}");
    delete presets[name];
    localStorage.setItem("job-viz-focus-presets", JSON.stringify(presets));
    renderPresets();
  }

  function renderPresets() {
    const list = $("#preset-list");
    const presets = JSON.parse(localStorage.getItem("job-viz-focus-presets") || "{}");
    list.innerHTML = "";
    Object.keys(presets).forEach((name) => {
      const tag = document.createElement("span");
      tag.className = "preset-tag";
      const load = document.createElement("button");
      load.type = "button";
      load.className = "preset-load";
      load.textContent = name;
      load.addEventListener("click", () => {
        state.focus = Object.assign({}, presets[name]);
        syncControls();
        dirtyFocus = true;
      });
      const del = document.createElement("button");
      del.type = "button";
      del.className = "preset-del";
      del.textContent = "x";
      del.title = "Delete preset";
      del.addEventListener("click", (ev) => { ev.stopPropagation(); deletePreset(name); });
      tag.appendChild(load);
      tag.appendChild(del);
      list.appendChild(tag);
    });
  }

  function copyFocus() {
    const f = state.focus;
    const payload = {
      cx: f.sx, cy: f.sy, cz: f.sz, radius: f.radius, boundary: f.boundary,
      label: { x: axisName("x", f.sx), y: axisName("y", f.sy), z: axisName("z", f.sz) },
      boundary_label: BOUNDARY_LABELS[f.boundary],
      search_bias: {
        x_range: [+(f.sx - f.radius).toFixed(1), +(f.sx + f.radius).toFixed(1)],
        y_range: [+(f.sy - f.radius).toFixed(1), +(f.sy + f.radius).toFixed(1)],
        z_range: [+(f.sz - f.radius * 0.8).toFixed(1), +(f.sz + f.radius * 0.8).toFixed(1)],
      },
    };
    const text = "/pipeline\n\nSearch focus from job_search_viz.html:\nSEARCH_FOCUS=" + JSON.stringify(payload);
    navigator.clipboard.writeText(text).then(() => {
      $("#health-readout").textContent = "Focus copied";
      setTimeout(() => { $("#health-readout").textContent = "Three.js renderer ready"; }, 1600);
    });
  }

  function screenshot() {
    const a = document.createElement("a");
    a.href = renderer.domElement.toDataURL("image/png");
    a.download = "job_search_space.png";
    a.click();
  }

  function bindUi() {
    $(".sidebar").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "color") {
        state.colorMode = btn.dataset.mode;
        $$("[data-group='color'] .btn").forEach((b) => b.classList.toggle("active", b === btn));
        if (state.colorMode === "location") state.showMap = true;
        dirtyScene = dirtyMap = true;
      }
      if (action === "toggle-labels") {
        state.showLabels = !state.showLabels;
        btn.classList.toggle("active", state.showLabels);
        // Grey out the nested label-fade controls when labels are off
        const fd = $("#label-fade-details");
        if (fd) fd.classList.toggle("labels-off", !state.showLabels);
      }
      if (action === "toggle-connections") { state.showConnections = !state.showConnections; btn.classList.toggle("active", state.showConnections); dirtyScene = true; }
      if (action === "toggle-coverage") {
        state.showCoverage = !state.showCoverage;
        if (coverageGroup) coverageGroup.visible = state.showCoverage;
        btn.classList.toggle("active", state.showCoverage);
        if (state.showCoverage) refreshCoverage();
      }
      if (action === "toggle-cov-past") { state.covPast = !state.covPast; btn.classList.toggle("active", state.covPast); refreshCoverage(); }
      if (action === "toggle-cov-future") { state.covFuture = !state.covFuture; btn.classList.toggle("active", state.covFuture); refreshCoverage(); }
      if (action === "toggle-salary-rings") { state.showSalaryRings = !state.showSalaryRings; btn.classList.toggle("active", state.showSalaryRings); dirtyScene = true; }
      if (action === "toggle-map") { state.showMap = !state.showMap; dirtyMap = true; }
      if (action === "map-back") { mapBack(); }
      if (action === "reset-camera") resetCamera();
      if (action === "screenshot") screenshot();
      if (action === "copy-focus") copyFocus();
      if (action === "save-preset") savePreset();
      if (action === "clear-status") { state.filters.statuses.clear(); $$(".pill").forEach((p) => p.classList.add("off")); dirtyFilter = true; }
      if (action === "reset-filters") resetFilters();
    });

    // The map overlay lives inside #scene-wrap, not the sidebar, so its
    // data-action buttons never reach the sidebar's delegated handler. Bind a
    // dedicated listener on the overlay for its own buttons (Back / Close).
    document.getElementById("map-overlay").addEventListener("click", (ev) => {
      // Pie axis switcher inside the hover popup — separate from data-action so it
      // never bubbles into the sidebar's delegated handler.
      // Pie axis switcher — header buttons (.map-pie-sw) or legacy popup buttons (.pie-axis-btn)
      const pieBtn = ev.target.closest(".map-pie-sw, .pie-axis-btn");
      if (pieBtn && pieBtn.dataset.pieAxis) {
        ev.stopPropagation();
        state.mapPieAxis = pieBtn.dataset.pieAxis;
        // Sync header button active states
        $$(".map-pie-sw").forEach(b => b.classList.toggle("active", b.dataset.pieAxis === state.mapPieAxis));
        refreshHoverPie();
        return;
      }
      const btn = ev.target.closest("[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "map-back") { mapBack(); }
      if (action === "toggle-map") { state.showMap = false; dirtyMap = true; }
      if (action === "map-select-all") {
        if (state.mapTier === "countries") state.filters.country = null;
        else state.filters.province = null;
        dirtyFilter = true; dirtyMap = true;
      }
      if (action === "map-deselect-all") {
        if (state.mapTier === "countries") state.filters.country = "__none__";
        else state.filters.province = "__none__";
        dirtyFilter = true; dirtyMap = true;
      }
    });

    $("#filter-text").addEventListener("input", (ev) => { state.filters.text = ev.target.value.toLowerCase(); dirtyFilter = true; });
    $("#fit-floor").addEventListener("input", (ev) => { state.filters.fitFloor = parseInt(ev.target.value, 10); updateFilterLabels(); dirtyFilter = true; });
    $("#salary-min").addEventListener("input", (ev) => { state.filters.salaryMin = parseInt(ev.target.value, 10); updateFilterLabels(); dirtyFilter = true; });
    $("#salary-max").addEventListener("input", (ev) => { state.filters.salaryMax = parseInt(ev.target.value, 10); updateFilterLabels(); dirtyFilter = true; });

    $("#label-zoom").addEventListener("input", (ev) => {
      state.labelZoom = parseInt(ev.target.value, 10);
      $("#label-zoom-value").textContent = state.labelZoom;
    });
    $("#label-fade").addEventListener("input", (ev) => {
      state.labelFade = parseInt(ev.target.value, 10);
      $("#label-fade-value").textContent = state.labelFade;
    });

    $$("[data-focus]").forEach((input) => {
      input.addEventListener("input", () => {
        const key = input.dataset.focus;
        state.focus[key] = key === "boundary" ? parseInt(input.value, 10) : parseFloat(input.value);
        updateFocusLabels();
        dirtyFocus = true;
      });
    });

    $("#detail").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action='cycle-outcome']");
      if (btn) cycleOutcome(btn.dataset.jobId);
    });

    $("#tl-start").addEventListener("input", updateTimelineFromControls);
    $("#tl-end").addEventListener("input", updateTimelineFromControls);
    const tlPlayBtn = $("#tl-play");
    if (tlPlayBtn) tlPlayBtn.addEventListener("click", function () {
      tlPlaying = !tlPlaying;
      this.innerHTML = tlPlaying ? "❚❚ Pause" : "▶ Play";
      if (tlPlaying) tlPlayStep();
    });
    const spd = $("#tl-speed");
    if (spd) spd.addEventListener("input", () => { tlSpeed = +spd.value; $("#tl-speed-val").innerHTML = tlSpeed + "&times;"; });
    const zm = $("#tl-zoom");
    if (zm) zm.addEventListener("input", () => {
      const span = 100 / (+zm.value), c = (state.timeline.startPct + state.timeline.endPct) / 2;
      $("#tl-zoom-val").innerHTML = (+zm.value) + "&times;";
      setScale(span, c);
    });
    const fv = $("#focus-vis");
    if (fv) {
      fv.checked = state.showFocus;
      fv.addEventListener("change", () => {
        state.showFocus = fv.checked;
        if (focusPoints) focusPoints.visible = state.showFocus;
        if (focusOutline) focusOutline.visible = state.showFocus;
      });
    }
    const sumTog = document.querySelector(".sum-tog");
    if (sumTog) sumTog.addEventListener("click", (e) => e.stopPropagation());
    document.querySelectorAll(".tl-preset").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".tl-preset").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      const d = b.dataset.days, c0 = (state.timeline.startPct + state.timeline.endPct) / 2;
      if (d === "all") setScale(100, 50);
      else if (d === "fit") setScale(state.timeline.endPct - state.timeline.startPct, c0);
      else { const span = Math.min(100, daysToPct(+d)); setScale(span, 100 - span / 2); }
    }));
    document.body.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action='reset-timeline']");
      if (btn) resetTimeline();
    });
  }

  function updateTimelineFromControls() {
    let s = parseFloat($("#tl-start").value), e = parseFloat($("#tl-end").value);
    if (s > e) { const t = s; s = e; e = t; $("#tl-start").value = s; $("#tl-end").value = e; }
    state.timeline.startPct = s;
    state.timeline.endPct = e;
    state.timeline.startDate = s <= 0.05 ? null : pctToDate(s);
    state.timeline.endDate = e >= 99.95 ? null : pctToDate(e);
    updateTimelineLabels();
    dirtyFilter = true;
    refreshCoverage();
    renderEntityStrip();
    renderTimelineTicks();
  }

  let tlPlaying = false, tlSpeed = 1;
  const THUMB = 14;                          // native range thumb px, for tick/handle alignment
  let vLo = 0, vHi = 100;                    // visible view range (pct of full timeline)
  const totalDays = Math.max(1, (dateMs(maxDate) - dateMs(minDate)) / 86400000);
  let ovTimer = null;
  function trackPx(box) { const cW = box.clientWidth || 1; return { cW, tW: Math.max(1, cW - THUMB), off: THUMB / 2 }; }
  function pctToViewFrac(p) { return (p - vLo) / Math.max(0.001, vHi - vLo); }
  function daysToPct(d) { return d / totalDays * 100; }

  // Single entry point: set the window (handles) AND the zoomed view (+margin), then redraw all.
  function setScale(spanPct, centerPct) {
    spanPct = Math.max(daysToPct(0.5), Math.min(100, spanPct));
    let ws = centerPct - spanPct / 2, we = centerPct + spanPct / 2;
    if (ws < 0) { we -= ws; ws = 0; } if (we > 100) { ws -= (we - 100); we = 100; } ws = Math.max(0, ws);
    const m = Math.min(ws, 100 - we, (we - ws) * 0.12);        // context margin around the window
    vLo = Math.max(0, ws - m); vHi = Math.min(100, we + m);
    const a = $("#tl-start"), b = $("#tl-end");
    a.min = vLo.toFixed(3); a.max = vHi.toFixed(3); a.step = "0.05"; a.value = ws.toFixed(3);
    b.min = vLo.toFixed(3); b.max = vHi.toFixed(3); b.step = "0.05"; b.value = we.toFixed(3);
    state.timeline.startPct = ws; state.timeline.endPct = we;
    state.timeline.startDate = ws <= 0.05 ? null : pctToDate(ws);
    state.timeline.endDate = we >= 99.95 ? null : pctToDate(we);
    dirtyFilter = true;
    updateTimelineLabels(); renderTimelineTicks(); renderEntityStrip(); refreshCoverage();
    if (vHi - vLo < 99.5) showOverview();
  }
  function showOverview() {
    const ov = $("#tl-overview"), bx = $("#tl-ov-box"); if (!ov || !bx) return;
    const g = trackPx(ov);
    bx.style.left = (g.off + (vLo / 100) * g.tW).toFixed(1) + "px";
    bx.style.width = Math.max(3, ((vHi - vLo) / 100) * g.tW).toFixed(1) + "px";
    ov.style.opacity = "1";
    if (ovTimer) clearTimeout(ovTimer);
    ovTimer = setTimeout(() => { ov.style.opacity = "0"; }, 2600);
  }
  function tlPlayStep() {
    if (!tlPlaying) return;
    const span = state.timeline.endPct - state.timeline.startPct;
    let c = (state.timeline.startPct + state.timeline.endPct) / 2 + 0.35 * tlSpeed;
    if (c - span / 2 > 100) c = span / 2;   // loop
    setScale(span, c);
    requestAnimationFrame(tlPlayStep);
  }
  function setLastMonthWindow() {
    const span = Math.min(100, daysToPct(30));
    setScale(span, 100 - span / 2);         // frame the most recent ~month
  }

  // Per-entity strip above the timeline: one tick+label per dated sweep,
  // strongest at the sliding-window centre, with greedy label de-overlap.
  function dateToPct(iso) {
    const a = dateMs(minDate), b = dateMs(maxDate);
    return b > a ? ((dateMs(iso) - a) / (b - a)) * 100 : 0;
  }
  function buildEntityStrip() {
    const box = $("#tl-entities"); if (!box) return;
    const sw = (DATA.coverage && DATA.coverage.sweeps) || [];
    sw.forEach((s) => {
      const wrap = document.createElement("div"); wrap.className = "tl-ent";
      const lb = document.createElement("div"); lb.className = "lb"; lb.textContent = shortCov(s.label);
      const tk = document.createElement("div"); tk.className = "tk";
      const dot = document.createElement("div"); dot.className = "dot";
      wrap.appendChild(lb); wrap.appendChild(tk); wrap.appendChild(dot);
      box.appendChild(wrap);
      entityEls.push({ wrap, lb, tk, dot, pct: dateToPct(s.date) });
    });
  }
  function renderEntityStrip() {
    const box = $("#tl-entities"); if (!box || !entityEls.length) return;
    const g = trackPx(box);
    const s = state.timeline.startPct, e = state.timeline.endPct;
    const centerPct = (s + e) / 2, halfWin = Math.max(0.5, (e - s) / 2);
    const order = entityEls.map((o) => ({ o, d: Math.abs(o.pct - centerPct) })).sort((a, b) => a.d - b.d);
    const placed = [];
    entityEls.forEach((o) => { o.wrap.style.display = "none"; });
    order.forEach(({ o }) => {
      if (o.pct < vLo - 0.5 || o.pct > vHi + 0.5) return;
      const x = g.off + pctToViewFrac(o.pct) * g.tW;
      const emph = Math.max(0, 1 - Math.abs(o.pct - centerPct) / (halfWin * 1.4));  // 1 at window centre
      const inWin = o.pct >= s && o.pct <= e;
      o.wrap.style.display = "";
      o.wrap.style.left = x.toFixed(1) + "px";
      o.tk.style.height = (4 + emph * 12).toFixed(0) + "px";
      o.tk.style.background = inWin ? (emph > 0.5 ? "#e0c2ff" : "#a487d8") : "#5a4f7a";
      o.dot.style.background = inWin ? "#c9a3ff" : "#5a4f7a";
      o.dot.style.opacity = (0.3 + 0.7 * emph).toFixed(2);
      const estW = o.lb.textContent.length * 5.2 + 8;
      const lo = x - estW / 2, hi = x + estW / 2;
      const overlap = placed.some((p) => !(hi < p.lo || lo > p.hi));
      const showLabel = emph > 0.05 && !overlap && x > estW / 2 - 3 && x < g.cW - estW / 2 + 3;
      o.lb.style.display = showLabel ? "" : "none";
      o.lb.style.opacity = (0.4 + 0.6 * emph).toFixed(2);
      o.lb.style.fontWeight = emph > 0.6 ? "700" : (emph > 0.3 ? "600" : "500");
      o.lb.style.color = inWin ? "#d9c4f5" : "#8a7fa8";
      if (showLabel) placed.push({ lo, hi });
    });
  }

  function boot() {
    if (!JOBS.length) return;
    renderStatusPills();
    renderRoleList();
    renderDetail();
    renderPresets();
    renderMap();
    renderTimelineTicks();
    buildEntityStrip();
    syncControls();
    bindUi();
    setLastMonthWindow();
    applyFilters();
    initThree();
  }

  boot();
})();
</script>
</body>
</html>
"""
    return html.replace("__PAYLOAD__", payload)


def vendor_three() -> None:
    """Place three.js beside the output so the viz never needs a network.

    The library used to load from a CDN, which quietly made the headline
    visualization of a local-first repo depend on jsdelivr being up and on the
    machine being online. It is vendored at assets/vendor/ and copied next to
    the generated HTML, so the same relative path works opened as a file and
    served over HTTP.
    """
    src = ROOT / "assets" / "vendor" / "three.min.js"
    dest = OUT.parent / "vendor" / "three.min.js"
    if not src.exists():
        print(f"!! {src.relative_to(ROOT).as_posix()} missing — the viz will not render.")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)


def main() -> None:
    jobs = enrich_jobs(load_legacy_jobs())
    backup_existing()
    html = build_html(jobs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    vendor_three()
    center = job_center(jobs)
    print(f"Written: {OUT}")
    print(f"Three.js job viz: {len(jobs)} roles; center X={center['x']:.2f} Y={center['y']:.2f} Z={center['z']:.2f}")


if __name__ == "__main__":
    main()
