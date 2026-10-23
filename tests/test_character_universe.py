import unittest
from unittest.mock import patch

import character_universe as cu
from character_universe import personagem_para_prompt


class TestCharacterUniverse(unittest.TestCase):
    def test_prompt_personagem_oficial_preserva_identidade(self):
        p = {'nome': 'Mel', 'dna': {'caracteristicas_bloqueadas': 'olhos verdes; laço vermelho'}}
        out = personagem_para_prompt(p, 'line_art')
        self.assertIn('Mel', out)
        self.assertIn('olhos verdes', out)
        self.assertIn('line_art', out)

    def _storage_patches(self, initial):
        store = {k: v.copy() if isinstance(v, dict) else list(v) for k, v in initial.items()}

        def fake_json(path, default):
            value = store.get(path, default)
            if isinstance(value, dict):
                return {**value}
            if isinstance(value, list):
                return [dict(x) for x in value]
            return value

        def fake_save(path, value):
            store[path] = value

        return store, patch.multiple(
            cu,
            _json=fake_json,
            _save_json=fake_save,
            persistir_assets_em_objeto=lambda obj, prefix: obj,
            materializar_assets_em_objeto=lambda obj: obj,
        )

    def test_detecta_mesmo_nome_em_colecoes_diferentes(self):
        initial = {
            cu.INDEX: [
                {'id': 'mel-canon', 'nome': 'Mel', 'colecao': cu.MEL_CANONICAL_COLLECTION, 'status': 'oficial'},
                {'id': 'mel-old', 'nome': 'Mel', 'colecao': 'Coleção Antiga', 'status': 'oficial'},
                {'id': 'teo', 'nome': 'Téo', 'colecao': cu.MEL_CANONICAL_COLLECTION, 'status': 'oficial'},
            ]
        }
        _, patches = self._storage_patches(initial)
        with patches:
            duplicados = cu.detectar_personagens_mesmo_nome('Mel')
        self.assertIn('mel', duplicados)
        self.assertEqual(2, len(duplicados['mel']))
        self.assertEqual({cu.MEL_CANONICAL_COLLECTION, 'Coleção Antiga'}, {x['colecao'] for x in duplicados['mel']})

    def test_arquivar_duplicada_preserva_dna_masters_referencias_e_historico(self):
        personagem = {
            'id': 'mel-old', 'nome': 'Mel', 'colecao': 'Coleção Antiga', 'status': 'oficial',
            'dna': {'descricao_master': 'DNA antigo'}, 'color_master': 'fb://color.png',
            'line_art_master': 'fb://line.png', 'reference_pack': [{'asset': 'fb://ref.png'}],
            'variacoes': [{'id': 'v1'}], 'versoes': [{'salvo_em': 1, 'snapshot': {'x': 1}}],
            'metadata': {'master_history': [{'asset_id': 'a1'}], 'current_master_asset_ids': {'color_master': 'a1'}},
        }
        initial = {
            cu.INDEX: [{'id': 'mel-old', 'nome': 'Mel', 'colecao': 'Coleção Antiga', 'status': 'oficial'}],
            'character_universe/mel-old.json': personagem,
        }
        store, patches = self._storage_patches(initial)
        with patches:
            archived = cu.arquivar_personagem('mel-old')
        self.assertEqual('arquivado', archived['status'])
        self.assertEqual('DNA antigo', archived['dna']['descricao_master'])
        self.assertEqual('fb://color.png', archived['color_master'])
        self.assertEqual('fb://line.png', archived['line_art_master'])
        self.assertEqual(1, len(archived['reference_pack']))
        self.assertEqual(1, len(archived['variacoes']))
        self.assertGreaterEqual(len(archived['versoes']), 2)
        self.assertEqual('arquivado', store[cu.INDEX][0]['status'])

    def test_mel_canonica_com_color_master_e_reference_pack_nao_pode_ser_arquivada(self):
        personagem = {
            'id': 'mel-canon', 'nome': 'Mel', 'colecao': cu.MEL_CANONICAL_COLLECTION, 'status': 'oficial',
            'dna': {'descricao_master': 'DNA oficial'}, 'color_master': 'fb://mel-master.png',
            'reference_pack': [{'asset': 'fb://mel-ref.png'}], 'metadata': {}, 'variacoes': [], 'versoes': [],
        }
        initial = {
            cu.INDEX: [{'id': 'mel-canon', 'nome': 'Mel', 'colecao': cu.MEL_CANONICAL_COLLECTION, 'status': 'oficial'}],
            'character_universe/mel-canon.json': personagem,
        }
        _, patches = self._storage_patches(initial)
        with patches:
            with self.assertRaises(PermissionError):
                cu.arquivar_personagem('mel-canon')

    def test_character_master_com_historico_exige_confirmacao_para_exclusao_permanente(self):
        personagem = {
            'id': 'p1', 'nome': 'P1', 'colecao': 'C', 'status': 'oficial',
            'dna': {}, 'color_master': 'fb://master.png', 'reference_pack': [],
            'metadata': {}, 'variacoes': [], 'versoes': [],
        }
        initial = {cu.INDEX: [], 'character_universe/p1.json': personagem}
        _, patches = self._storage_patches(initial)
        with patches:
            with self.assertRaises(PermissionError):
                cu.validar_exclusao_permanente('p1', confirmacao_explicita=False)
            self.assertTrue(cu.validar_exclusao_permanente('p1', confirmacao_explicita=True))

    def test_move_teo_para_colecao_correta_preserva_id_referencias_masters_e_historico(self):
        personagem = {
            'id': 'teo-1', 'nome': 'Téo', 'colecao': 'Histórias que florescem da Vida', 'status': 'oficial',
            'dna': {'descricao_master': 'Passarinho azul'},
            'color_master': 'fb://teo-master.png', 'line_art_master': 'fb://teo-line.png',
            'reference_pack': [{'asset': 'fb://teo-1.png'}, {'asset': 'fb://teo-2.png'}, {'asset': 'fb://teo-3.png'}],
            'metadata': {'master_history': [{'asset_id': 'teo-master'}]},
            'variacoes': [{'id': 'v1'}], 'versoes': [],
        }
        initial = {
            cu.INDEX: [{'id': 'teo-1', 'nome': 'Téo', 'colecao': 'Histórias que florescem da Vida', 'status': 'oficial'}],
            'character_universe/teo-1.json': personagem,
        }
        store, patches = self._storage_patches(initial)
        with patches:
            moved = cu.mover_personagem_para_colecao(
                'teo-1', cu.MEL_CANONICAL_COLLECTION, confirmacao_explicita=True,
            )
        self.assertEqual('teo-1', moved['id'])
        self.assertEqual(cu.MEL_CANONICAL_COLLECTION, moved['colecao'])
        self.assertEqual(3, len(moved['reference_pack']))
        self.assertEqual('fb://teo-master.png', moved['color_master'])
        self.assertEqual('fb://teo-line.png', moved['line_art_master'])
        self.assertEqual(1, len(moved['variacoes']))
        self.assertTrue(moved['metadata']['collection_history'])
        self.assertEqual('Histórias que florescem da Vida', moved['metadata']['collection_history'][-1]['de'])
        self.assertEqual(cu.MEL_CANONICAL_COLLECTION, moved['metadata']['collection_history'][-1]['para'])
        self.assertEqual(cu.MEL_CANONICAL_COLLECTION, store[cu.INDEX][0]['colecao'])

    def test_move_de_colecao_exige_confirmacao_explicita(self):
        personagem = {
            'id': 'teo-1', 'nome': 'Téo', 'colecao': 'Errada', 'status': 'oficial',
            'dna': {}, 'reference_pack': [], 'metadata': {}, 'variacoes': [], 'versoes': [],
        }
        initial = {
            cu.INDEX: [{'id': 'teo-1', 'nome': 'Téo', 'colecao': 'Errada', 'status': 'oficial'}],
            'character_universe/teo-1.json': personagem,
        }
        _, patches = self._storage_patches(initial)
        with patches:
            with self.assertRaises(PermissionError):
                cu.mover_personagem_para_colecao('teo-1', 'Correta', confirmacao_explicita=False)

    def test_move_bloqueia_colisao_de_nome_na_colecao_destino(self):
        teo_errado = {
            'id': 'teo-old', 'nome': 'Téo', 'colecao': 'Errada', 'status': 'oficial',
            'dna': {}, 'reference_pack': [], 'metadata': {}, 'variacoes': [], 'versoes': [],
        }
        teo_existente = {
            'id': 'teo-right', 'nome': 'Téo', 'colecao': 'Correta', 'status': 'oficial',
            'dna': {}, 'reference_pack': [], 'metadata': {}, 'variacoes': [], 'versoes': [],
        }
        initial = {
            cu.INDEX: [
                {'id': 'teo-old', 'nome': 'Téo', 'colecao': 'Errada', 'status': 'oficial'},
                {'id': 'teo-right', 'nome': 'Téo', 'colecao': 'Correta', 'status': 'oficial'},
            ],
            'character_universe/teo-old.json': teo_errado,
            'character_universe/teo-right.json': teo_existente,
        }
        _, patches = self._storage_patches(initial)
        with patches:
            with self.assertRaises(ValueError):
                cu.mover_personagem_para_colecao('teo-old', 'Correta', confirmacao_explicita=True)


if __name__ == '__main__':
    unittest.main()
