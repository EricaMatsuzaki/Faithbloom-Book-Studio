import tempfile
import unittest
import fila_producao as fp
from storage_backend import LocalStorageBackend

class TestFilaProducao(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        fp.BACKEND=LocalStorageBackend(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pausa_continua_cancela(self):
        j=fp.criar_job('x','teste',[{'kind':'x'},{'kind':'x'}],state={'n':0})
        self.assertEqual(j['status'],'fila')
        self.assertEqual(fp.pausar_job(j['id'])['status'],'pausado')
        self.assertEqual(fp.continuar_job(j['id'])['status'],'fila')
        self.assertEqual(fp.cancelar_job(j['id'])['status'],'cancelado')

    def test_checkpoint_e_conclusao(self):
        j=fp.criar_job('x','teste',[{'kind':'x'},{'kind':'x'}],state={'n':0})
        def executor(job,item):
            s=dict(job['state']); s['n']+=1
            return s, {'feito':True}
        j=fp.processar_proximo(j['id'],executor)
        self.assertEqual(j['state']['n'],1)
        self.assertEqual(fp.resumo_job(j)['concluidos'],1)
        j=fp.processar_proximo(j['id'],executor)
        self.assertEqual(j['status'],'concluido')
        self.assertEqual(j['state']['n'],2)

    def test_recupera_interrompido_sem_repetir(self):
        j=fp.criar_job('x','teste',[{'kind':'x'}],state={})
        j['status']='executando'; fp.salvar_job(j)
        ids=fp.recuperar_jobs_interrompidos()
        self.assertIn(j['id'],ids)
        self.assertEqual(fp.carregar_job(j['id'])['status'],'pausado')

if __name__=='__main__': unittest.main()
