# This source code is part of the Biotite package and is distributed
# under the 3-Clause BSD License. Please see 'LICENSE.rst' for further
# information.

"""
This module provides one function for the computation of the partial
charges of the individual atoms of a given AtomArray according to the
PEOE algorithm of Gasteiger-Marsili.
"""

__name__ = "biotite.charges"
__author__ = "Jacob Marcel Anter"
__all__ = ["partial_charges"]

import warnings
import numpy as np
from .info import residue
from biotite.structure import AtomArray, BondType


# Creating two dictionaries to retrieve parameters for electronegativity
# computation from
# The first dictionary uses BondTypes as keys, whereas the second uses
# the amounts of binding partners as keys
# First level of dictionaries represents the atom name and the second
# level represents the hybridisation state
# Depending on whether the bond type is unequal to zero or not,
# identification of the hybridisation state is either performed via the
# first dictionary, i. e. the bond type (primary way of identification
# since erroneous results are excluded) or via the second dictionary,
# i. e. amount of binding partners (erroneous if a binding partner is
# lost or added whilst the hybridisation remains unchanged as it is the
# case with acids or bases, e. g. the hydroxyl group in a carboxyl
# group: When the proton involved in the hydroxyl group is donated, the
# amount of binding partners of the remaining oxygen is one; this would
# erroneously lead to an identification of the hybridisation state as
# sp2 although it is still sp3)
EN_PARAM_BTYPE = {
    "H": {
        BondType.SINGLE:   (7.17, 6.24, -0.56)
    },

    "C": {
        BondType.SINGLE:   (7.98, 9.18, 1.88),
        BondType.DOUBLE:   (8.79, 9.18, 1.88),
        BondType.TRIPLE:   (10.39, 9.45, 0.73),
        BondType.AROMATIC: (8.79, 9.18, 1.88)
    },

    "N": {
        BondType.SINGLE:   (11.54, 10.82, 1.36),
        BondType.DOUBLE:   (12.87, 11.15, 0.85),
        BondType.TRIPLE:   (15.68, 11.7, -0.27)
    },

    # As oxygen and sulfur are exclusively involved in aromatic
    # systems having single bonds on either side, the values for a
    # sp3 hybridisation are taken for BondType.AROMATIC
    "O": {
        BondType.SINGLE:   (14.18, 12.92, 1.39),
        BondType.DOUBLE:   (17.07, 13.79, 0.47),
        BondType.AROMATIC: (14.18, 12.92, 1.39)
    },

    "S": {
        BondType.SINGLE:   (10.14, 9.13, 1.38),
        BondType.AROMATIC: (10.14, 9.13, 1.38)
    },

    "F": {
        BondType.SINGLE:   (14.66, 13.85, 2.31)
    },

    "Cl": {
        BondType.SINGLE:   (11.00, 9.69, 1.35)
    },

    "Br": {
        BondType.SINGLE:   (10.08, 8.47, 1.16)
    },

    "I": {
        BondType.SINGLE:   (9.90, 7.96, 0.96)
    }        
}

EN_PARAM_BPARTNERS = {
    "H": {
        1: (7.17, 6.24, -0.56)
    },

    "C": {
        4: (7.98, 9.18, 1.88),
        3: (8.79, 9.18, 1.88),
        2: (10.39, 9.45, 0.73)
    },

    "N": {
        # Considering protonated, e. g. in terminal
        # amino group (4 binding partners), as well
        # as unprotonated nitrogen (3 binding partners)
        4: (11.54, 10.82, 1.36),
        3: (11.54, 10.82, 1.36),
        2: (12.87, 11.15, 0.85),
        1: (15.68, 11.7, -0.27)
    },

    "O": {
        2: (14.18, 12.92, 1.39),
        1: (17.07, 13.79, 0.47)
    },

    "S": {
        2: (10.14, 9.13, 1.38)
    },

    "F": {
        1: (14.66, 13.85, 2.31)
    },

    "Cl": {
        1: (11.00, 9.69, 1.35)
    },

    "Br": {
        1: (10.08, 8.47, 1.16)
    },

    "I": {
        1: (9.90, 7.96, 0.96)
    }
}


# Defining constant for the special case of the electronegativity of
# positively charged hydrogen (value given in electronvolt, as all
# electronegativity values)
EN_POS_HYDROGEN = 20.02


def _determine_aromatic_nitrogen_hybridisation(
    elements, types, bond_types, charges
):
    """
    Determine whether a nitrogen atom involved in an aromatic system
    possesses exclusively single bonds or one double bond as well.

    The need to determine this arises from the fact that the assignment
    of parameters for electronegativity computation is based on the
    hybridisation state, i. e. no special parameters for the involvement
    in aromatic systems are available. This poses no problem in the case
    of the elements oxygen and sulfur as they are exclusively involved
    in aromatic systems having single bonds on either side, enabling the
    the assignment of aromaticity to a distinct hybridisation state.
    Nitrogen, however, can be involved in aromatic systems having both
    exclusively single bonds as well as one double bond, making the
    assignment of aromaticity to a distinct hybridisation state
    impossible. Examples for nitrogen atoms involved in an aromatic
    system having exclusively single bonds as well as one double bond
    within one and the same molecule are the aromatic compounds
    'imidazole' and 'pyrazole'.

    Parameters
    ----------
    elements: ndarray, dtype=str
        The array comprising the elements of the inserted `atom_array`.
    types: ndarray, shape=(n,m), dtype=int
        The array containing the bond types of each bond of every atom.
    bond_types: ndarray, dtype=int
        The array containing information about the highest bond type of
        the respective atom (except for BondType.AROMATIC).
    charges: ndarray, dtype=int
        Array that comprises the formal charges of the atoms comprised
        in the `atom_array` inserted into the `partial_charges`
        function.

    Returns
    -------
    bond_types: ndarray, dtype=int
        The inserted array in which the BondType.AROMATIC is replaced by
        the a BondType revealing the bond order in case of nitrogen
        atoms.
    """

    aromatic_nitrogen_indices = np.where(
        (elements == "N") & (bond_types == BondType.AROMATIC)
    )[0]
    for i in aromatic_nitrogen_indices:
        considered_row = types[i]
        # Aromaticity implies molecular cyclicality, i. e.
        # an atom involved in an aromatic system has at
        # least two bonds with the aromatic bond type
        # Nitrogen has at most three bonds if involved in an
        # aromatic system, where the third bond type is
        # BondType.SINGLE
        # Therefore, the presence of a third bond type
        # indicates a sp3 hybridisation, whereas the absence
        # of a third bond type can be either due to sp2
        # hybridisation or deprotonation
        # In order to account for this ambiguity, the charge
        # is considered in case that a third bond type is
        # not present
        if considered_row.shape[0] >= 3:
            bond_types[i] = BondType.SINGLE
        else:
            nitrogen_charge = charges[i]
            if nitrogen_charge == -1:
                bond_types[i] = BondType.SINGLE
            else:
                bond_types[i] =  BondType.DOUBLE
    
    return bond_types


def _get_parameters(elements, bond_types, amount_of_binding_partners):
    """
    Gather the parameters required for electronegativity computation of
    all atoms comprised in the input array `elements`.

    By doing so, the function accesses the nested dictionary
    ``EN_PARAMETERS``. The values originate from a publication of Johann
    Gasteiger and Mario Marsili. [1]_

    Parameters
    ----------
    elements: ndarray, dtype=str
        The array comprising the elements which to retrieve the
        parameters for.
    bond_types: ndarray, dtype=int
        The array containing information about the highest bond type of
        the respective atom (except for BondType.AROMATIC).
    amount_of_binding_partners: ndarray, dtype=int
        The array containing information about the amount of binding
        partners of the respective atom.
    
    Returns
    -------
    parameters: NumPy array, dtype=float, shape=(n,3)
        The array containing all three parameters required for the
        computation of the electronegativities of all atoms comprised
        in the `elements` array.
    
    References
    ----------
    .. [1] J Gasteiger and M Marsili,
       "Iterative partial equalization of orbital electronegativity - a
       rapid access to atomic charges"
       Tetrahedron, 36, 3219 - 3288 (1980).
    """

    parameters = np.zeros((elements.shape[0], 3))

    has_atom_key_error = False
    has_valence_key_error = False
    each_btype_equal_zero = False
    some_btype_equal_zero = False

    # The length of `bond_types` is zero in case of an AtomArray
    # consisting of atoms that are not connected to each other, e. g. if
    # the AtomArray exclusively contains ions
    # The length the array must be checked as well as `any` and `all`
    # evaluate to true if the iterable is empty
    if (np.all(bond_types == BondType.ANY)
        and
        bond_types.shape[0] != 0):
        each_btype_equal_zero = True
    elif (np.any(bond_types == BondType.ANY)
        and
        bond_types.shape[0] != 0):
        some_btype_equal_zero = True
    
    # Preparing warning in case of KeyError
    # It is differentiated between atoms that are not parametrized at
    # all and specific valence states that are parametrized
    list_of_unparametrized_elements = []
    unparametrized_valences = []
    unparam_valence_names = []
    list_of_atoms_without_specified_btype = []

    for i, element in enumerate(elements):
        # Considering the special case of ions
        if amount_of_binding_partners[i] == 0:
            parameters[i, :] = np.nan
            continue
        if bond_types[i] == BondType.ANY:
            characteristic = amount_of_binding_partners[i]
            list_of_atoms_without_specified_btype.append(str(i))
            try:
                a, b, c = EN_PARAM_BPARTNERS[element][characteristic]
                parameters[i, 0] = a
                parameters[i, 1] = b
                parameters[i, 2] = c
            except KeyError:
                try:
                    EN_PARAM_BPARTNERS[element]
                except KeyError:
                    list_of_unparametrized_elements.append(element)
                    has_atom_key_error = True
                else:
                    # The warning message printed in case of
                    # unparametrized valence states contains its main
                    # information in a table with three columns:
                    # The first column represents the element, the
                    # second the amount of binding partners and the
                    # third the BondType
                    # The primary way of identifying unparametrized
                    # valence states that is aimed at is via the
                    # BondType; if this is possible, the space beneath
                    # the column representing the amount of binding
                    # partners is padded with a respective amount the
                    # '-' (hyphen) character
                    # If not, the space beneath the column representing
                    # the BondTypes is padded with a respective amount
                    # of hyphens
                    # At either case, an appropriate amount of
                    # whitespace is added in order to ensure that the
                    # respective entries appear directly under the
                    # respective columns
                    unparam_valence_names.append(element)
                    unparametrized_valences.append(
                        str(amount_of_binding_partners[i])
                        +
                        " " * 31
                        +
                        "-" * 10
                    )
                    has_valence_key_error = True
                parameters[i, :] = np.nan
        else:
            characteristic = bond_types[i]
            try:
                a, b, c = EN_PARAM_BTYPE[element][characteristic]
                parameters[i, 0] = a
                parameters[i, 1] = b
                parameters[i, 2] = c
            except KeyError:
                try:
                    EN_PARAM_BTYPE[element]
                except KeyError:
                    list_of_unparametrized_elements.append(element)
                    has_atom_key_error = True
                else:
                    unparam_valence_names.append(element)
                    unparametrized_valences.append(
                        "-" * 27
                        +
                        " " * 5
                        +
                        str(bond_types[i])
                    )
                    has_valence_key_error = True
                parameters[i, :] = np.nan
        
    if some_btype_equal_zero:
        warnings.warn(
            f"Some atoms' bond type is unspecified, i. e. the bond "
            f"type is given as `any`. For these atoms, identification "
            f"of the hybridisation state is performed via the amount "
            f"of binding partners which can lead to erroneous results."
            f"\n\n"
            f"In detail, these atoms possess the following indices: \n"
            f"{', '. join(list_of_atoms_without_specified_btype)}.",
            UserWarning
        )

    if each_btype_equal_zero:
        warnings.warn(
            f"Each atom's bond type is 0 (any). Therefore, it is "
            f"resorted to the amount of binding partners for the "
            f"identification of the hybridisation state which can lead "
            f"to erroneous results.",
            UserWarning
        )

    if has_valence_key_error:
        joined_list = []
        for i in range(len(unparam_valence_names)):
            joined_list.append(
                unparam_valence_names[i].ljust(2, ' ')
                +
                " " * 8
            )
            joined_list.append(unparametrized_valences[i] + "\n")
        joined_array = np.reshape(
            joined_list,
            newshape=(int(len(joined_list) / 2), 2)
        )
        joined_array = np.unique(joined_array, axis=0)
        # Array must be flattened in order ro be able to apply the
        # 'join' method
        flattened_joined_array = np.reshape(
            joined_array, newshape=(2*joined_array.shape[0])
        )
        warnings.warn(
            f"Parameters for specific valence states of some atoms "
            f"are not available. These valence states are: \n"
            f"Atom:     Amount of binding partners:     Bond type:\n"
            f"{''.join(flattened_joined_array)}"
            f"Their electronegativity is given as NaN.",
            UserWarning
        )

    if has_atom_key_error:
        # Using NumPy's 'unique' function to ensure that each atom only
        # occurs once in the list
        unique_list = np.unique(list_of_unparametrized_elements)
        # Considering proper punctuation for the warning string
        warnings.warn(
            f"Parameters required for computation of "
            f"electronegativity aren't available for the following "
            f"atoms: {', '.join(unique_list)}. "
            f"Their electronegativity is given as NaN.", 
            UserWarning
        )

    return parameters


def partial_charges(atom_array, iteration_step_num=6, charges=None):
    """
    Compute the partial charge of the individual atoms comprised in a
    given :class:`AtomArray` depending on their electronegativity.

    This function implements the
    *partial equalization of orbital electronegativity* (PEOE)
    algorithm [1]_.

    Parameters
    ----------
    atom_array: AtomArray, shape=(n,)
        The :class:`AtomArray` to get the partial charge values for.
        Must have an associated `BondList`.
    iteration_step_num: int, optional
        The number of iteration steps is an optional argument and can be 
        chosen by the user depending on the desired precision of the
        result. If no value is entered by the user, the default value
        '6' will be used.
        Gasteiger and Marsili described this number as sufficient [1]_.
    charges: ndarray, dtype=int, optional
        The array comprising the formal charges of the atoms in the
        input `atom_array`.
        If none is given, the ``charge`` annotation category of the
        input `atom_array` is used.
        If neither of them is given, the formal charges of all atoms
        will be arbitrarily set to zero.
    
    Returns
    -------
    charges: ndarray, dtype=float
        The partial charge values of the individual atoms in the input
        `atom_array`.
    
    Notes
    -----
    A :class:`BondList` must be associated to the input
    :class:`AtomArray`.
    Otherwise, an error will be raised.
    Example:

    .. code-block:: python

        atom_array.bonds = struc.connect_via_residue_names(atom_array)

    |

    For the electronegativity of positively charged hydrogen, the
    value of 20.02 eV is used.

    Also note that the algorithm used in this function does not deliver
    proper results for expanded pi-electron systems like aromatic rings.

    References
    ----------
    .. [1] J Gasteiger and M Marsili,
       "Iterative partial equalization of orbital electronegativity- a
       rapid access to atomic charges"
       Tetrahedron, 36, 3219 - 3288 (1980).

    Examples
    --------
    The molecule fluoromethane is taken as example since detailed
    information is given about the charges of this molecule in each
    iteration step in the respective publication of Gasteiger and
    Marsili. [1]_

    >>> fluoromethane = residue("CF0")
    >>> print(fluoromethane.atom_name)
    ['C1' 'F1' 'H1' 'H2' 'H3']
    >>> print(partial_charges(fluoromethane, iteration_step_num=1))
    [ 0.115 -0.175  0.020  0.020  0.020]
    >>> print(partial_charges(fluoromethane, iteration_step_num=6))
    [ 0.079 -0.253  0.058  0.058  0.058]
    """
    
    if atom_array.bonds is None:
        raise AttributeError(
            f"The input AtomArray doesn't possess an associated "
            f"BondList."
        )
    if charges is None:
        try:
            # Implicitly this creates a copy of the charges
            charges = atom_array.charge.astype(np.float)
        except AttributeError:
            charges = np.zeros(atom_array.shape[0])
            warnings.warn(
                f"A charge array was neither given as optional "
                f"argument, nor does a charge annotation of the "
                f"inserted AtomArray exist. Therefore, all atoms' "
                f"formal charge is assumed to be zero.",
                UserWarning
            )

    elements = atom_array.element
    bonds, types = atom_array.bonds.get_all_bonds()
    amount_of_binding_partners = np.count_nonzero(bonds != -1, axis=1)

    # The maximum of a given row of the `types` array must be determined
    # as this value reveals the hybridisation state
    # An atom's overall BondType is assumed to be ANY as soon as one
    # BondType.ANY occurs
    try:
        bond_types = np.amax(types, axis=1)
    except ValueError:
        bond_types = np.array([])
    else:
        zero_indices_in_first_dim = np.unique(
            np.nonzero(types == BondType.ANY)[0]
        )
        bond_types[zero_indices_in_first_dim] = BondType.ANY
        if "N" in elements:
            bond_types = _determine_aromatic_nitrogen_hybridisation(
                elements, types, bond_types, charges
            )
            
    damping = 1.0
    parameters = _get_parameters(
        elements, bond_types, amount_of_binding_partners
    )
    # Computing electronegativity values in case of positive charge
    # which enter as divisor the equation for charge transfer
    pos_en_values = np.sum(parameters, axis=1)
    # Substituting values for hydrogen with the special value
    pos_en_values[atom_array.element == "H"] = EN_POS_HYDROGEN

    for _ in range(iteration_step_num):
        # In the beginning of each iteration step, the damping factor is 
        # halved in order to guarantee rapid convergence
        damping *= 0.5
        # For performing matrix-matrix-multiplication, the array
        # containing the charges, the array containing the squared
        # charges and another array consisting of entries of '1' and
        # having the same length as the previous two are converted into
        # column vectors and then merged to one array
        column_charges = np.transpose(np.atleast_2d(charges))
        sq_column_charges = np.transpose(np.atleast_2d(charges**2))
        ones_vector = np.transpose(
            np.atleast_2d(np.full(atom_array.shape[0], 1))
        )
        charge_array = np.concatenate(
            (ones_vector, column_charges,sq_column_charges), axis=1
        )
        en_values = np.sum(parameters * charge_array, axis=1)
        for i, j, _ in atom_array.bonds.as_array():
            # For atoms that are not available in the dictionary,
            # but which are incorporated into molecules,
            # the partial charge is set to NaN
            if np.isnan(en_values[[i, j]]).any():
                # Determining for which atom exactly no parameters are
                # available is necessary since the other atom, for which
                # there indeed are parameters, could be involved in
                # multiple bonds.
                # Therefore, setting both charges to NaN would falsify
                # the result.
                # The case that both atoms are not parametrized must be
                # considered as well.
                if np.isnan(en_values[i]):
                    charges[i] = np.nan
                if np.isnan(en_values[j]):
                    charges[j] = np.nan
            else:
                if en_values[j] > en_values[i]:
                    divisor = pos_en_values[i]
                else:
                    divisor = pos_en_values[j]
                charge_transfer = ((en_values[j] - en_values[i]) /
                    divisor) * damping
                charges[i] += charge_transfer
                charges[j] -= charge_transfer

    return charges