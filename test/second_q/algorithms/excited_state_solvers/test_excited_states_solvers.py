# This code is part of Qiskit.
#
# (C) Copyright IBM 2020, 2023.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

""" Test Numerical qEOM excited states calculation """

import unittest

from test import QiskitNatureTestCase
from ddt import ddt, named_data
import numpy as np

from qiskit.algorithms.eigensolvers import NumPyEigensolver
from qiskit.algorithms.minimum_eigensolvers import NumPyMinimumEigensolver
from qiskit.algorithms.optimizers import SLSQP
from qiskit.primitives import Estimator
from qiskit.utils import algorithm_globals

from qiskit_nature.units import DistanceUnit
from qiskit_nature.second_q.circuit.library import UCCSD
from qiskit_nature.second_q.transformers import ActiveSpaceTransformer
from qiskit_nature.second_q.drivers import PySCFDriver
from qiskit_nature.second_q.mappers import (
    BravyiKitaevMapper,
    JordanWignerMapper,
    ParityMapper,
)
from qiskit_nature.second_q.mappers import QubitConverter
from qiskit_nature.second_q.algorithms import (
    GroundStateEigensolver,
    VQEUCCFactory,
    NumPyEigensolverFactory,
    ExcitedStatesEigensolver,
    QEOM,
)
import qiskit_nature.optionals as _optionals


@ddt
class TestNumericalQEOMESCCalculation(QiskitNatureTestCase):
    """Test Numerical qEOM excited states calculation"""

    @unittest.skipIf(not _optionals.HAS_PYSCF, "pyscf not available.")
    def setUp(self):
        super().setUp()
        algorithm_globals.random_seed = 8
        self.driver = PySCFDriver(
            atom="H .0 .0 .0; H .0 .0 0.75",
            unit=DistanceUnit.ANGSTROM,
            charge=0,
            spin=0,
            basis="sto3g",
        )

        self.reference_energies = [
            -1.8427016,
            -1.8427016 + 0.5943372,
            -1.8427016 + 0.95788352,
            -1.8427016 + 1.5969296,
        ]
        self.mapper = JordanWignerMapper()
        self.qubit_converter = QubitConverter(self.mapper)
        self.electronic_structure_problem = self.driver.run()

        solver = NumPyEigensolver()
        self.ref = solver

    def _assert_energies(self, computed, references, *, places=4):
        with self.subTest("same number of energies"):
            self.assertEqual(len(computed), len(references))

        with self.subTest("ground state"):
            self.assertAlmostEqual(computed[0], references[0], places=places)

        for i in range(1, len(computed)):
            with self.subTest(f"{i}. excited state"):
                self.assertAlmostEqual(computed[i], references[i], places=places)

    def test_numpy_mes(self):
        """Test NumPyMinimumEigenSolver with QEOM"""
        solver = NumPyMinimumEigensolver()
        gsc = GroundStateEigensolver(self.qubit_converter, solver)
        esc = QEOM(gsc, Estimator(), "sd")
        results = esc.solve(self.electronic_structure_problem)
        self._assert_energies(results.computed_energies, self.reference_energies)

    @named_data(
        ["JWM", QubitConverter(JordanWignerMapper())],
        ["JWM_Z2", QubitConverter(JordanWignerMapper(), z2symmetry_reduction="auto")],
        ["PM", QubitConverter(ParityMapper())],
        ["PM_TQR", QubitConverter(ParityMapper(), two_qubit_reduction=True)],
        ["PM_Z2", QubitConverter(ParityMapper(), z2symmetry_reduction="auto")],
        [
            "PM_TQR_Z2",
            QubitConverter(ParityMapper(), two_qubit_reduction=True, z2symmetry_reduction="auto"),
        ],
        ["BKM", QubitConverter(BravyiKitaevMapper())],
        ["BKM_Z2", QubitConverter(BravyiKitaevMapper(), z2symmetry_reduction="auto")],
    )
    def test_solve_with_vqe_mes(self, converter: QubitConverter):
        """Test QEOM with VQEUCCFactory and various QubitConverter"""

        estimator = Estimator()
        solver = VQEUCCFactory(estimator, UCCSD(), SLSQP())
        gsc = GroundStateEigensolver(converter, solver)
        esc = QEOM(gsc, estimator, "sd")
        results = esc.solve(self.electronic_structure_problem)
        self._assert_energies(results.computed_energies, self.reference_energies)

    def test_numpy_factory(self):
        """Test NumPyEigenSolverFactory with ExcitedStatesEigensolver"""

        # pylint: disable=unused-argument
        def filter_criterion(eigenstate, eigenvalue, aux_values):
            return np.isclose(aux_values["ParticleNumber"][0], 2.0)

        solver = NumPyEigensolverFactory(filter_criterion=filter_criterion)
        esc = ExcitedStatesEigensolver(self.qubit_converter, solver)
        results = esc.solve(self.electronic_structure_problem)

        # filter duplicates from list
        computed_energies = [results.computed_energies[0]]
        for comp_energy in results.computed_energies[1:]:
            if not np.isclose(comp_energy, computed_energies[-1]):
                computed_energies.append(comp_energy)

        self._assert_energies(computed_energies, self.reference_energies)

    def test_custom_filter_criterion(self):
        """Test NumPyEigenSolverFactory with ExcitedStatesEigensolver + Custom filter criterion
        for doublet states"""

        driver = PySCFDriver(
            atom="Be .0 .0 .0; H .0 .0 0.75",
            unit=DistanceUnit.ANGSTROM,
            charge=0,
            spin=1,
            basis="sto3g",
        )

        transformer = ActiveSpaceTransformer((1, 2), 4)
        # We define an ActiveSpaceTransformer to reduce the duration of this test example.

        converter = QubitConverter(JordanWignerMapper(), z2symmetry_reduction="auto")

        esp = transformer.transform(driver.run())

        expected_spin = 0.75  # Doublet states
        expected_num_electrons = 3  # 1 alpha electron + 2 beta electrons

        # pylint: disable=unused-argument
        def custom_filter_criterion(eigenstate, eigenvalue, aux_values):
            num_particles_aux = aux_values["ParticleNumber"][0]
            total_angular_momentum_aux = aux_values["AngularMomentum"][0]

            return np.isclose(total_angular_momentum_aux, expected_spin) and np.isclose(
                num_particles_aux, expected_num_electrons
            )

        solver = NumPyEigensolverFactory(filter_criterion=custom_filter_criterion)
        esc = ExcitedStatesEigensolver(converter, solver)
        results = esc.solve(esp)

        # filter duplicates from list
        computed_energies = [results.computed_energies[0]]
        for comp_energy in results.computed_energies[1:]:
            if not np.isclose(comp_energy, computed_energies[-1]):
                computed_energies.append(comp_energy)

        ref_energies = [
            -2.6362023196223254,
            -2.2971398524128923,
            -2.2020252702733165,
            -2.1044859216523752,
            -1.696132447109807,
            -1.6416831059956618,
        ]

        self._assert_energies(computed_energies, ref_energies, places=3)

    @unittest.skipIf(not _optionals.HAS_PYSCF, "pyscf not available.")
    def test_solver_compatibility_with_mappers(self):
        """Test that solvers can use both QubitConverter and QubitMapper"""

        # pylint: disable=unused-argument
        def filter_criterion(eigenstate, eigenvalue, aux_values):
            return np.isclose(aux_values["ParticleNumber"][0], 2.0)

        with self.subTest("Excited states solver with qubit converter"):
            solver = NumPyEigensolverFactory(filter_criterion=filter_criterion)
            esc_converter = ExcitedStatesEigensolver(self.qubit_converter, solver)
            results_converter = esc_converter.solve(self.electronic_structure_problem)
            computed_energies_converter = [results_converter.computed_energies[0]]
            # filter duplicates from list
            for comp_energy in results_converter.computed_energies[1:]:
                if not np.isclose(comp_energy, computed_energies_converter[-1]):
                    computed_energies_converter.append(comp_energy)
            self._assert_energies(computed_energies_converter, self.reference_energies)

        with self.subTest("Excited states solver with qubit mapper"):
            solver = NumPyEigensolverFactory(filter_criterion=filter_criterion)
            esc_mapper = ExcitedStatesEigensolver(self.mapper, solver)
            results_mapper = esc_mapper.solve(self.electronic_structure_problem)
            # filter duplicates from list
            computed_energies_mapper = [results_mapper.computed_energies[0]]
            for comp_energy in results_mapper.computed_energies[1:]:
                if not np.isclose(comp_energy, computed_energies_mapper[-1]):
                    computed_energies_mapper.append(comp_energy)
            self._assert_energies(computed_energies_mapper, self.reference_energies)

        with self.subTest("QEOM with qubit converter"):
            estimator = Estimator()
            solver = VQEUCCFactory(estimator, UCCSD(), SLSQP())
            gsc_converter = GroundStateEigensolver(self.qubit_converter, solver)
            esc_converter = QEOM(gsc_converter, estimator, "sd")
            results_converter = esc_converter.solve(self.electronic_structure_problem)
            # filter duplicates from list
            computed_energies_converter = [results_converter.computed_energies[0]]
            for comp_energy in results_converter.computed_energies[1:]:
                if not np.isclose(comp_energy, computed_energies_converter[-1]):
                    computed_energies_converter.append(comp_energy)
            self._assert_energies(computed_energies_converter, self.reference_energies)

        with self.subTest("QEOM with qubit mapper"):
            estimator = Estimator()
            solver = VQEUCCFactory(estimator, UCCSD(), SLSQP())
            gsc_mapper = GroundStateEigensolver(self.mapper, solver)
            esc_mapper = QEOM(gsc_mapper, estimator, "sd")
            results_mapper = esc_mapper.solve(self.electronic_structure_problem)
            # filter duplicates from list
            computed_energies_mapper = [results_mapper.computed_energies[0]]
            for comp_energy in results_mapper.computed_energies[1:]:
                if not np.isclose(comp_energy, computed_energies_mapper[-1]):
                    computed_energies_mapper.append(comp_energy)
            self._assert_energies(computed_energies_mapper, self.reference_energies)


if __name__ == "__main__":
    unittest.main()
