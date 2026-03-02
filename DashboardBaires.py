import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import plotly.express as px

# ==============================
# 🔌 CONEXIÓN A SUPABASE
# ==============================
def conectar():
    """
    Conecta a la base de datos usando el Secret DATABASE_URL.
    """
    try:
        conn = psycopg2.connect(st.secrets["DATABASE_URL"])
        return conn
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None


# ==============================
# 🔐 LOGIN
# ==============================

if "login" not in st.session_state:
    st.session_state.login = False

def login():
    st.image("logo.png", width=200)
    st.title("🔐 Iniciar Sesión")

    usuario = st.text_input("Usuario", key="login_usuario_unique")
    clave = st.text_input("Contraseña", type="password", key="login_clave_unique")

    if st.button("Entrar", key="login_btn_unique"):
        conn = conectar()

        # 🔥 VALIDACIÓN IMPORTANTE
        if conn is None:
            st.stop()

        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM usuarios WHERE TRIM(usuario)=%s AND TRIM(clave)=%s",
                (usuario.strip(), clave.strip())
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                st.session_state["login"] = True
                st.success(f"¡Bienvenido, {usuario}!")
                st.experimental_rerun()
            else:
                st.error("Usuario o contraseña incorrecta")

        except Exception as e:
            st.error(f"Error durante el login: {e}")
            conn.close()


# ==============================
# 📊 DASHBOARD
# ==============================

def dashboard():
    conn = conectar()

    # 🔥 VALIDACIÓN IMPORTANTE
    if conn is None:
        st.stop()

    cur = conn.cursor()

    query = """
        SELECT 
            c.nombre,
            COALESCE(SUM(CASE WHEN m.tipo='venta' THEN m.monto END),0) as total,
            COALESCE(SUM(CASE WHEN m.tipo='pago' THEN m.monto END),0) as pagado
        FROM clientes c
        LEFT JOIN movimientos m ON c.id = m.cliente_id
        GROUP BY c.nombre
    """

    df = pd.read_sql(query, conn)
    df["pendiente"] = df["total"] - df["pagado"]

    total_deuda = df["pendiente"].sum()
    total_pagado = df["pagado"].sum()
    total_general = df["total"].sum()

    st.title("📊 Dashboard AppBaires")
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total que deben", f"${total_deuda:,.2f}")
    col2.metric("✅ Total pagado", f"${total_pagado:,.2f}")
    col3.metric("📦 Total general", f"${total_general:,.2f}")

    grafico_df = pd.DataFrame({
        "Estado": ["Pendiente", "Pagado"],
        "Monto": [total_deuda, total_pagado]
    })

    fig = px.bar(grafico_df, x="Estado", y="Monto",
                 color="Estado",
                 color_discrete_map={"Pendiente":"red", "Pagado":"green"})

    st.plotly_chart(fig)

    mensual = """
        SELECT DATE_TRUNC('month', fecha) as mes,
               SUM(CASE WHEN tipo='venta' THEN monto ELSE 0 END) as ventas,
               SUM(CASE WHEN tipo='pago' THEN monto ELSE 0 END) as pagos
        FROM movimientos
        GROUP BY mes
        ORDER BY mes
    """

    df_mensual = pd.read_sql(mensual, conn)
    st.subheader("📅 Resumen Mensual")
    st.dataframe(df_mensual)

    st.subheader("📋 Detalle de Clientes")
    st.dataframe(df)

    st.subheader("✔ Registrar Pago")
    clientes = df["nombre"].tolist()
    cliente_select = st.selectbox("Selecciona cliente", clientes, key="cliente_select_unique")
    monto_pago = st.number_input("Monto que pagó", min_value=0.0, key="monto_pago_unique")

    if st.button("Guardar Pago", key="guardar_pago_unique"):
        try:
            cliente_id_query = "SELECT id FROM clientes WHERE nombre=%s"
            cur.execute(cliente_id_query, (cliente_select,))
            cliente_data = cur.fetchone()

            if cliente_data:
                cliente_id = cliente_data[0]

                insertar = """
                    INSERT INTO movimientos (cliente_id, tipo, monto, fecha)
                    VALUES (%s, 'pago', %s, %s)
                """
                cur.execute(insertar, (cliente_id, monto_pago, datetime.now()))
                conn.commit()

                st.success("Pago registrado correctamente")
                st.experimental_rerun()
            else:
                st.error("Cliente no encontrado")

        except Exception as e:
            st.error(f"Error al registrar pago: {e}")

    st.subheader("📊 Estadísticas de Ventas")

    try:
        diaria = """
            SELECT SUM(monto) FROM movimientos
            WHERE tipo='venta' AND DATE(fecha)=CURRENT_DATE
        """
        cur.execute(diaria)
        ventas_diarias = cur.fetchone()[0] or 0

        semanal = """
            SELECT SUM(monto) FROM movimientos
            WHERE tipo='venta'
            AND fecha >= date_trunc('week', CURRENT_DATE)
        """
        cur.execute(semanal)
        ventas_semanales = cur.fetchone()[0] or 0

        mensual_query = """
            SELECT SUM(monto) FROM movimientos
            WHERE tipo='venta'
            AND fecha >= date_trunc('month', CURRENT_DATE)
        """
        cur.execute(mensual_query)
        ventas_mensuales = cur.fetchone()[0] or 0

        anual_query = """
            SELECT SUM(monto) FROM movimientos
            WHERE tipo='venta'
            AND fecha >= date_trunc('year', CURRENT_DATE)
        """
        cur.execute(anual_query)
        ventas_anuales = cur.fetchone()[0] or 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hoy", f"${ventas_diarias:,.2f}")
        c2.metric("Semana", f"${ventas_semanales:,.2f}")
        c3.metric("Mes", f"${ventas_mensuales:,.2f}")
        c4.metric("Año", f"${ventas_anuales:,.2f}")

    except Exception as e:
        st.error(f"Error en estadísticas: {e}")

    conn.close()


# ==============================
# 🚀 MAIN
# ==============================

if not st.session_state["login"]:
    login()
else:
    dashboard()