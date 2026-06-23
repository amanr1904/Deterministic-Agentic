import json
ir = json.load(open(r"Output/Active2021Q3DealerBuyingEvent/analysis.json", encoding="utf-8"))
ws = ir.get("worksheets", [])
print("WORKSHEETS:", len(ws))
for w in ws:
    print("|".join([
        w.get("name","")[:34].ljust(34),
        str(w.get("mark"))[:10].ljust(10),
        str(w.get("inferredVisualType"))[:12].ljust(12),
        ("cat="+str(w.get("categoryField")))[:30].ljust(30),
        ("val="+str(w.get("valueField")))[:30],
    ]))
print("\nDASHBOARDS:")
for d in ir.get("dashboards", []):
    zones=d.get("zones",[])
    vz=[z for z in zones if z.get("type")=="viz"]
    print(d.get("name"), d.get("size"), "zones",len(zones),"viz",len(vz))
