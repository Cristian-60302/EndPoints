import os

from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


def get_connection():
    return psycopg2.connect(
        host="ep-raspy-scene-b4o7810q-pooler.c-6.us-east-2.aws.neon.tech",
        database="neondb",
        user="neondb_owner",
        password="npg_VZ5WOEoTB2CA",
        sslmode="require",
        channel_binding="require"
    )
##

# =========================================================
# ENDPOINT 1 - LOGIN
# POST /login
# =========================================================

@app.route("/login", methods=["POST"])
def login():

    try:
        data = request.get_json()

        correo = data.get("correo")
        password = data.get("password")

        if not correo or not password:
            return jsonify({
                "error": "Correo y contraseña son obligatorios"
            }), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                u.id_usuario,
                u.nombre,
                u.correo,
                u.password,
                e.id_empresa,
                e.nombre AS empresa
            FROM usuarios u
            INNER JOIN empresas e
                ON u.id_empresa = e.id_empresa
            WHERE u.correo = %s
        """, (correo,))

        usuario = cursor.fetchone()

        cursor.close()
        conn.close()

        if usuario is None:
            return jsonify({
                "error": "Correo o contraseña incorrectos"
            }), 401

        if password != usuario["password"]:
            return jsonify({
                "error": "Correo o contraseña incorrectos"
            }), 401

        # No devolver la contraseña
        del usuario["password"]

        return jsonify({
            "mensaje": "Login exitoso",
            "usuario": usuario
        })

    except Exception as e:

        print(e)

        return jsonify({
            "error": "Error interno del servidor"
        }), 500


# =========================================================
# ENDPOINT 2 - CONSULTAR PRODUCTOS
# GET /productos?id_empresa=1
# =========================================================

@app.route("/productos", methods=["GET"])
def obtener_productos():

    try:

        id_empresa = request.args.get("id_empresa")

        if not id_empresa:
            return jsonify({
                "error": "Debe enviar id_empresa"
            }), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                p.id_producto,
                p.nombre,
                p.descripcion,
                p.marca,
                c.nombre AS categoria
            FROM productos p
            INNER JOIN categorias c
                ON p.id_categoria = c.id_categoria
            WHERE p.id_empresa = %s
            ORDER BY p.id_producto
        """, (id_empresa,))

        productos = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "empresa": id_empresa,
            "cantidad": len(productos),
            "productos": productos
        })

    except Exception as e:

        print(e)

        return jsonify({
            "error": "Error consultando productos"
        }), 500


# =========================================================
# ENDPOINT 3 - AGREGAR OBJETO AL INVENTARIO
# POST /inventario
# =========================================================

@app.route("/inventario", methods=["POST"])
def agregar_inventario():

    try:

        data = request.get_json()

        id_producto = data.get("id_producto")
        codigo = data.get("codigo")
        estado = data.get("estado", "Disponible")
        ubicacion = data.get("ubicacion")

        if not id_producto or not codigo:
            return jsonify({
                "error": "id_producto y codigo son obligatorios"
            }), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            INSERT INTO inventario
            (
                id_producto,
                codigo,
                estado,
                ubicacion
            )
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (
            id_producto,
            codigo,
            estado,
            ubicacion
        ))

        objeto = cursor.fetchone()

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "mensaje": "Objeto agregado correctamente",
            "objeto": objeto
        }), 201

    except psycopg2.errors.UniqueViolation:

        return jsonify({
            "error": "El código del objeto ya existe"
        }), 409

    except psycopg2.errors.ForeignKeyViolation:

        return jsonify({
            "error": "El producto indicado no existe"
        }), 400

    except Exception as e:

        print(e)

        return jsonify({
            "error": "Error agregando objeto al inventario"
        }), 500


# =========================================================
# ENDPOINT 4 - RESUMEN DEL INVENTARIO
# GET /inventario/resumen?id_empresa=1
# =========================================================

@app.route("/inventario/resumen", methods=["GET"])
def resumen_inventario():

    try:

        id_empresa = request.args.get("id_empresa")

        if not id_empresa:
            return jsonify({
                "error": "Debe enviar id_empresa"
            }), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                p.id_producto,
                p.nombre AS producto,

                COUNT(i.id_objeto) AS total,

                COUNT(*) FILTER (
                    WHERE i.estado = 'Disponible'
                ) AS disponibles,

                COUNT(*) FILTER (
                    WHERE i.estado = 'Dañado'
                ) AS danados,

                COUNT(*) FILTER (
                    WHERE i.estado = 'Prestado'
                ) AS prestados,

                COUNT(*) FILTER (
                    WHERE i.estado = 'Vendido'
                ) AS vendidos

            FROM productos p

            LEFT JOIN inventario i
                ON p.id_producto = i.id_producto

            WHERE p.id_empresa = %s

            GROUP BY
                p.id_producto,
                p.nombre

            ORDER BY p.nombre
        """, (id_empresa,))

        resumen = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "empresa": id_empresa,
            "resumen": resumen
        })

    except Exception as e:

        print(e)

        return jsonify({
            "error": "Error generando resumen"
        }), 500


# =========================================================
# ENDPOINT 5 - ACTUALIZAR OBJETO
# PUT /inventario/<id>
# =========================================================

@app.route("/inventario/<int:id_objeto>", methods=["PUT"])
def actualizar_inventario(id_objeto):

    try:

        data = request.get_json()

        estado = data.get("estado")
        ubicacion = data.get("ubicacion")

        if not estado and not ubicacion:
            return jsonify({
                "error": "Debe enviar estado o ubicacion"
            }), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            UPDATE inventario

            SET
                estado = COALESCE(%s, estado),
                ubicacion = COALESCE(%s, ubicacion)

            WHERE id_objeto = %s

            RETURNING *
        """, (
            estado,
            ubicacion,
            id_objeto
        ))

        objeto = cursor.fetchone()

        if objeto is None:

            cursor.close()
            conn.close()

            return jsonify({
                "error": "Objeto no encontrado"
            }), 404

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "mensaje": "Objeto actualizado correctamente",
            "objeto": objeto
        })

    except Exception as e:

        print(e)

        return jsonify({
            "error": "Error actualizando inventario"
        }), 500


# =========================================================
# RUTA PRINCIPAL
# =========================================================

@app.route("/", methods=["GET"])
def inicio():

    return jsonify({
        "mensaje": "API de Inventarios funcionando",
        "endpoints": [
            "POST /login",
            "GET /productos?id_empresa=1",
            "POST /inventario",
            "GET /inventario/resumen?id_empresa=1",
            "PUT /inventario/<id>"
        ]
    })


# =========================================================
# INICIAR SERVIDOR
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=3000,
        debug=True
    )
