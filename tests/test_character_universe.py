import unittest
from character_universe import personagem_para_prompt
class TestCharacterUniverse(unittest.TestCase):
    def test_prompt_personagem_oficial_preserva_identidade(self):
        p={'nome':'Mel','dna':{'caracteristicas_bloqueadas':'olhos verdes; laço vermelho'}}
        out=personagem_para_prompt(p,'line_art')
        self.assertIn('Mel',out); self.assertIn('olhos verdes',out); self.assertIn('line_art',out)
if __name__=='__main__': unittest.main()
