import json, tempfile, unittest
from pathlib import Path
from openpyxl import Workbook
from pp_engine import PPProcessor

HEADERS=["DATE_SUBMITTED","CELL","Technology (2G/3G/4G)","STATE","LGA","2G Erlang ","Availability","CSSR","SDCCH Congestion Rate","TCH Congestion Rate","Drop Call Rate ","Handover Success Rate"]

class PPTests(unittest.TestCase):
    def build(self, duplicate=False):
        td=tempfile.TemporaryDirectory(); root=Path(td.name)
        cfg=root/"config"/"pp_config.json"; cfg.parent.mkdir()
        cfg.write_text(json.dumps({
            "operator":"Operator A","technology":"2G","minimum_kpi_completeness_for_model":0.8,
            "columns":{"date":"DATE_SUBMITTED","cell":"CELL","technology":"Technology (2G/3G/4G)","state":"STATE","lga":"LGA","traffic":"2G Erlang ","availability":"Availability","cssr":"CSSR","sd_congestion":"SDCCH Congestion Rate","tch_congestion":"TCH Congestion Rate","dcr":"Drop Call Rate ","hosr":"Handover Success Rate"}
        }))
        wb=Workbook(); ws=wb.active; ws.title="Day1"; ws.append(HEADERS)
        for i in range(10):
            cell="CELL_0" if duplicate and i==1 else f"CELL_{i}"
            cssr=104.0 if i==9 else 99.5
            ws.append(["2026-08-03",cell,"2G","FCT","AMAC",100+i,99.2,cssr,0.1,0.05,0.2,99.0])
        x=root/"sample.xlsx"; wb.save(x)
        return td,cfg,x

    def test_invalid_field_is_warning_not_whole_day_failure(self):
        td,cfg,x=self.build(False)
        try:
            s,v=PPProcessor(cfg).process_workbook(x)
            self.assertEqual(s[0].total_rows,10); self.assertTrue(s[0].model_eligible); self.assertEqual(s[0].quality_status,"WARNING")
            self.assertTrue(any(r["rule"]=="INVALID-RANGE" and r["field"]=="CSSR" for r in v))
        finally: td.cleanup()

    def test_duplicate_cell_blocks_model_eligibility(self):
        td,cfg,x=self.build(True)
        try:
            s,v=PPProcessor(cfg).process_workbook(x)
            self.assertFalse(s[0].model_eligible)
            self.assertTrue(any(r["rule"]=="CELL-DUPLICATE" for r in v))
        finally: td.cleanup()

if __name__=="__main__": unittest.main()
